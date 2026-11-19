"""Arabic static-letter recognition using the selected ArASL CNN model.

MediaPipe is used to locate one hand in webcam frames. The expanded hand ROI is
converted to grayscale 64x64 and normalized like the ArASL images. Camera framing
is still a domain gap and must be validated on real webcam samples. Handedness is
not a class.
"""
from collections import defaultdict, deque
from pathlib import Path
import time

import cv2
import numpy as np

ARABIC_LABELS = {
    "ain": "ع", "al": "ال", "aleff": "ا", "bb": "ب", "dal": "د",
    "dha": "ظ", "dhad": "ض", "fa": "ف", "gaaf": "ق",
    "ghain": "غ", "ha": "ه", "haa": "ح", "jeem": "ج",
    "kaaf": "ك", "khaa": "خ", "la": "لا", "laam": "ل", "meem": "م",
    "nun": "ن", "ra": "ر", "saad": "ص", "seen": "س",
    "sheen": "ش", "ta": "ط", "taa": "ت", "thaa": "ث", "toot": "ة",
    "thal": "ذ", "waw": "و", "ya": "ئ", "yaa": "ي", "zay": "ز",
}

HAND_CONNECTIONS = [
    (0,1),(1,2),(2,3),(3,4),(0,5),(5,6),(6,7),(7,8),
    (5,9),(9,10),(10,11),(11,12),(9,13),(13,14),(14,15),(15,16),
    (13,17),(17,18),(18,19),(19,20),(0,17),
]


class SignLanguageCNN:
    """Lazy torch model wrapper, keeping torch optional until sign page startup."""
    def __init__(self, num_classes):
        import torch.nn as nn
        self.module = nn.Module

        class Network(nn.Module):
            def __init__(self, count):
                super().__init__()
                self.features = nn.Sequential(
                    nn.Conv2d(1, 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU(inplace=True), nn.MaxPool2d(2),
                    nn.Conv2d(32, 64, 3, padding=1), nn.BatchNorm2d(64), nn.ReLU(inplace=True), nn.MaxPool2d(2),
                    nn.Conv2d(64, 128, 3, padding=1), nn.BatchNorm2d(128), nn.ReLU(inplace=True), nn.MaxPool2d(2),
                    nn.Conv2d(128, 256, 3, padding=1), nn.BatchNorm2d(256), nn.ReLU(inplace=True), nn.MaxPool2d(2),
                    nn.AdaptiveAvgPool2d((1, 1)),
                )
                self.classifier = nn.Sequential(
                    nn.Flatten(), nn.Linear(256, 128), nn.ReLU(inplace=True),
                    nn.Dropout(0.4), nn.Linear(128, count),
                )
            def forward(self, x):
                return self.classifier(self.features(x))
        self.network = Network(num_classes)


def preprocess_image(rgb: np.ndarray):
    """Match train_cnn.py eval_transform: grayscale, resize 64x64, normalize .5/.5."""
    if rgb is None or not isinstance(rgb, np.ndarray) or rgb.size == 0:
        raise ValueError("Empty image")
    if rgb.ndim == 2:
        gray = rgb
    elif rgb.shape[2] == 4:
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGBA2GRAY)
    else:
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    interpolation = cv2.INTER_AREA if min(gray.shape[:2]) >= 64 else cv2.INTER_CUBIC
    gray = cv2.resize(gray, (64, 64), interpolation=interpolation)
    tensor = gray.astype(np.float32) / 255.0
    tensor = (tensor - 0.5) / 0.5
    return tensor[None, None, :, :]


class SignLanguageService:
    def __init__(self, model_path=None, smoothing_window=7, num_hands=1,
                 min_live_confidence=0.40, min_margin=0.035):
        self.root = Path(__file__).resolve().parents[2]
        self.model_path = Path(model_path) if model_path else self.root / "models/cnn_baseline/best_cnn_model.pth"
        if not self.model_path.is_absolute():
            self.model_path = self.root / self.model_path
        self.model = None
        self.class_names = []
        self.device = "cpu"
        self.load_error = None
        self.landmarker = None
        self.hand_error = None
        self._last_timestamp_ms = 0
        self.num_hands = max(1, min(2, int(num_hands)))
        self.histories = defaultdict(lambda: deque(maxlen=max(5, int(smoothing_window))))
        self.label_histories = defaultdict(lambda: deque(maxlen=max(5, int(smoothing_window))))
        self.min_live_confidence = float(min_live_confidence)
        self.min_margin = float(min_margin)
        self.min_stable_votes = 5
        self._load_model()
        self._init_hand_detector()

    def _load_model(self):
        if not self.model_path.is_file():
            self.load_error = f"CNN model not found: {self.model_path}"
            return
        try:
            import torch
            bundle = torch.load(self.model_path, map_location="cpu", weights_only=True)
            self.class_names = list(bundle.get("class_names", []))
            if len(self.class_names) != 32 or set(self.class_names) != set(ARABIC_LABELS):
                raise ValueError("CNN checkpoint must contain exactly the 32 supported ArASL classes")
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            wrapper = SignLanguageCNN(len(self.class_names))
            wrapper.network.load_state_dict(bundle["model_state_dict"])
            self.model = wrapper.network.to(self.device).eval()
            self.torch = torch
            self.checkpoint_info = {
                "best_epoch": bundle.get("best_epoch"),
                "best_validation_accuracy": bundle.get("best_val_accuracy"),
                "image_size": bundle.get("image_size", 64),
            }
        except Exception as exc:
            self.load_error = f"{type(exc).__name__}: {exc}"
            self.model = None

    def _init_hand_detector(self):
        task_file = self.root / "models/mediapipe/hand_landmarker.task"
        if not task_file.is_file():
            self.hand_error = f"MediaPipe task file is missing: {task_file}"
            return
        try:
            import mediapipe as mp
            options = mp.tasks.vision.HandLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(model_asset_path=str(task_file)),
                running_mode=mp.tasks.vision.RunningMode.VIDEO,
                num_hands=self.num_hands,
                min_hand_detection_confidence=0.40,
                min_hand_presence_confidence=0.40,
                min_tracking_confidence=0.40,
            )
            self.landmarker = mp.tasks.vision.HandLandmarker.create_from_options(options)
        except Exception as exc:
            self.hand_error = f"{type(exc).__name__}: {exc}"

    @staticmethod
    def _to_rgb(frame_or_path):
        from PIL import Image
        if isinstance(frame_or_path, (str, Path)):
            with Image.open(frame_or_path) as image:
                return np.asarray(image.convert("RGB"))
        if not isinstance(frame_or_path, np.ndarray) or frame_or_path.size == 0:
            raise ValueError("Expected a valid image path or OpenCV frame")
        if frame_or_path.ndim == 2:
            return cv2.cvtColor(frame_or_path, cv2.COLOR_GRAY2RGB)
        if frame_or_path.shape[2] == 4:
            return cv2.cvtColor(frame_or_path, cv2.COLOR_BGRA2RGB)
        return cv2.cvtColor(frame_or_path, cv2.COLOR_BGR2RGB)

    def _probabilities(self, rgb):
        if self.model is None:
            raise RuntimeError(self.load_error or "CNN is not loaded")
        tensor = self.torch.from_numpy(preprocess_image(np.ascontiguousarray(rgb))).to(self.device)
        with self.torch.inference_mode():
            logits = self.model(tensor)
            probabilities = self.torch.softmax(logits, dim=1)[0].detach().cpu().numpy()
        return probabilities.astype(np.float32)

    @staticmethod
    def _top3(probabilities, class_names):
        order = np.argsort(probabilities)[::-1][:3]
        return [{
            "class_name": str(class_names[int(i)]),
            "label": ARABIC_LABELS[str(class_names[int(i)])],
            "confidence": float(probabilities[int(i)]),
        } for i in order]

    def predict(self, frame_or_path):
        rgb = self._to_rgb(frame_or_path)
        # Uploaded photos should use the same hand-centered input convention as live frames.
        if self.landmarker is not None:
            try:
                import mediapipe as mp
                timestamp_ms = max(int(time.monotonic_ns() // 1_000_000), self._last_timestamp_ms + 1)
                self._last_timestamp_ms = timestamp_ms
                result = self.landmarker.detect_for_video(
                    mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb)),
                    timestamp_ms,
                )
                if result.hand_landmarks:
                    rgb, _ = self._hand_roi(rgb, result.hand_landmarks[0])
            except Exception:
                pass
        probs = self._probabilities(rgb)
        top3 = self._top3(probs, self.class_names)
        margin = top3[0]["confidence"] - top3[1]["confidence"]
        accepted = top3[0]["confidence"] >= self.min_live_confidence and margin >= self.min_margin
        return {**top3[0], "accepted": accepted, "stable_frames": None,
                "agreement": 1.0, "margin": margin, "top3": top3, "hands": []}

    @staticmethod
    def _hand_roi(rgb, landmarks, padding=0.65):
        h, w = rgb.shape[:2]
        xs = np.asarray([float(p.x) * w for p in landmarks], dtype=np.float32)
        ys = np.asarray([float(p.y) * h for p in landmarks], dtype=np.float32)
        x1, x2, y1, y2 = float(xs.min()), float(xs.max()), float(ys.min()), float(ys.max())
        bw, bh = max(2.0, x2-x1), max(2.0, y2-y1)
        side = max(bw, bh) * (1.0 + 2.0 * padding)
        cx, cy = (x1+x2)/2.0, (y1+y2)/2.0
        left, top = int(round(cx-side/2)), int(round(cy-side/2))
        right, bottom = left+int(round(side)), top+int(round(side))
        pad_l, pad_t = max(0,-left), max(0,-top)
        pad_r, pad_b = max(0,right-w), max(0,bottom-h)
        crop = rgb[max(0,top):min(h,bottom), max(0,left):min(w,right)]
        if crop.size == 0:
            raise ValueError("Detected hand ROI is empty")
        if any((pad_l,pad_t,pad_r,pad_b)):
            crop = cv2.copyMakeBorder(crop, pad_t, pad_b, pad_l, pad_r,
                                      cv2.BORDER_REFLECT_101)
        margin_x, margin_y = max(5, int(bw*.08)), max(5, int(bh*.08))
        bbox = (max(0,int(xs.min())-margin_x), max(0,int(ys.min())-margin_y),
                min(w-1,int(xs.max())+margin_x), min(h-1,int(ys.max())+margin_y))
        return crop, bbox

    def process_frame(self, frame):
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
            raise ValueError("Empty camera frame")
        if self.landmarker is None:
            return {"hands": [], "hand_detected": False,
                    "error": self.hand_error or "MediaPipe is unavailable"}
        if self.model is None:
            return {"hands": [], "hand_detected": False,
                    "error": self.load_error or "CNN is unavailable"}
        import mediapipe as mp
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        timestamp_ms = max(int(time.monotonic_ns() // 1_000_000), self._last_timestamp_ms + 1)
        self._last_timestamp_ms = timestamp_ms
        result = self.landmarker.detect_for_video(
            mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb)), timestamp_ms)
        hands_out = []
        active_keys = set()
        for idx, landmarks in enumerate(result.hand_landmarks or []):
            key = f"hand_{idx+1}"
            active_keys.add(key)
            try:
                roi, bbox = self._hand_roi(rgb, landmarks)
                probs = self._probabilities(roi)
                history = self.histories[key]
                history.append(probs)
                averaged = np.mean(np.stack(history), axis=0)
                top3 = self._top3(averaged, self.class_names)
                votes = self.label_histories[key]
                votes.append(int(np.argmax(probs)))
                counts = np.bincount(list(votes), minlength=len(self.class_names))
                stable_index = int(np.argmax(counts))
                stable_votes = int(counts[stable_index])
                confidence = float(averaged[stable_index])
                ordered = np.sort(averaged)
                margin = float(ordered[-1] - ordered[-2])
                accepted = (
                    len(votes) >= 5 and stable_votes >= self.min_stable_votes and
                    confidence >= self.min_live_confidence and margin >= self.min_margin and
                    stable_index == int(np.argmax(averaged))
                )
                class_name = self.class_names[stable_index]
                hands_out.append({
                    "hand_id": key, "hand_number": idx+1, "bbox": bbox,
                    "landmarks": [(float(p.x), float(p.y)) for p in landmarks],
                    "label": ARABIC_LABELS[class_name] if accepted else "",
                    "candidate_label": top3[0]["label"], "class_name": class_name,
                    "confidence": confidence, "margin": margin,
                    "accepted": accepted, "stable_frames": len(votes),
                    "agreement": stable_votes / max(1, len(votes)), "top3": top3,
                })
            except Exception as exc:
                hands_out.append({"hand_id": key, "hand_number": idx+1,
                                  "accepted": False, "label": "",
                                  "error": f"{type(exc).__name__}: {exc}"})
        # Drop history for hands that disappeared, preventing stale votes being reused.
        for key in list(self.histories):
            if key not in active_keys:
                self.histories.pop(key, None)
                self.label_histories.pop(key, None)
        return {"hands": hands_out, "hand_detected": bool(hands_out)}

    def reset_smoothing(self):
        self.histories.clear()
        self.label_histories.clear()

    def close(self):
        if self.landmarker is not None:
            try:
                self.landmarker.close()
            except Exception:
                pass
            self.landmarker = None
