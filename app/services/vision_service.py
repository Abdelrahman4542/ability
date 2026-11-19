"""COCO object detection plus optional text-prompt open-vocabulary detection."""
from pathlib import Path
import cv2
import numpy as np


class VisionService:
    def __init__(self, weights_path="yolo11n.pt", confidence=0.30, image_size=960,
                 max_detections=100, iou=0.50):
        root = Path(__file__).resolve().parents[2]
        candidate = Path(weights_path)
        if not candidate.is_absolute():
            candidate = root / candidate
        self.weights_path = str(candidate)
        self.confidence = float(confidence)
        self.image_size = int(image_size)
        self.max_detections = int(max_detections)
        self.iou = float(iou)
        self.model = None
        self.error = None
        self.open_vocab_model = None
        self.open_vocab_processor = None
        self.open_vocab_error = None
        try:
            from ultralytics import YOLO
            if not candidate.is_file():
                raise FileNotFoundError(f"YOLO weights not found: {candidate}")
            self.model = YOLO(str(candidate))
        except Exception as exc:
            self.error = f"{type(exc).__name__}: {exc}"

    @staticmethod
    def _read_frame(frame_or_image_path):
        if isinstance(frame_or_image_path, (str, Path)):
            frame = cv2.imread(str(frame_or_image_path))
            if frame is None:
                raise ValueError(f"Could not read image: {frame_or_image_path}")
        else:
            frame = frame_or_image_path
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
            raise ValueError("No valid image/frame was provided.")
        return frame

    @staticmethod
    def _deduplicate(detections, threshold=0.78):
        detections.sort(key=lambda item: item["confidence"], reverse=True)
        kept = []
        for candidate in detections:
            ax1, ay1, ax2, ay2 = candidate["box"]
            area_a = max(0, ax2-ax1) * max(0, ay2-ay1)
            duplicate = False
            for current in kept:
                if candidate["label"].casefold() != current["label"].casefold():
                    continue
                bx1, by1, bx2, by2 = current["box"]
                inter = max(0, min(ax2,bx2)-max(ax1,bx1)) * max(0, min(ay2,by2)-max(ay1,by1))
                area_b = max(0,bx2-bx1) * max(0,by2-by1)
                union = area_a + area_b - inter
                if union and inter / union >= threshold:
                    duplicate = True
                    break
            if not duplicate:
                kept.append(candidate)
        return kept

    @staticmethod
    def _annotate(frame, detections):
        annotated = frame.copy()
        for item in detections:
            x1, y1, x2, y2 = item["box"]
            label = f'{item["label"]} {item["confidence"]:.0%}'
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (66, 214, 181), 2)
            text_y = max(22, y1 - 8)
            cv2.putText(annotated, label, (x1, text_y), cv2.FONT_HERSHEY_SIMPLEX,
                        0.65, (20, 45, 40), 3, cv2.LINE_AA)
            cv2.putText(annotated, label, (x1, text_y), cv2.FONT_HERSHEY_SIMPLEX,
                        0.65, (120, 245, 210), 1, cv2.LINE_AA)
        return annotated

    def detect(self, frame_or_image_path):
        if self.model is None:
            raise RuntimeError(f"YOLO is not ready. Details: {self.error}")
        frame = self._read_frame(frame_or_image_path)
        results = self.model.predict(
            source=frame, conf=self.confidence, iou=self.iou,
            imgsz=self.image_size, max_det=self.max_detections,
            agnostic_nms=False, verbose=False,
        )
        detections = []
        if results:
            result = results[0]
            names, boxes = result.names, result.boxes
            if boxes is not None:
                for box in boxes:
                    cls_id = int(box.cls.item())
                    conf = float(box.conf.item())
                    x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
                    detections.append({
                        "label": str(names.get(cls_id, cls_id)),
                        "confidence": conf, "box": [x1, y1, x2, y2],
                        "source": "YOLO",
                    })
        filtered = self._deduplicate(detections)
        return filtered, self._annotate(frame, filtered)

    def _load_open_vocabulary(self):
        if self.open_vocab_model is not None:
            return
        try:
            import torch
            from transformers import OwlViTProcessor, OwlViTForObjectDetection
            model_id = "google/owlvit-base-patch32"
            self.open_vocab_processor = OwlViTProcessor.from_pretrained(model_id)
            self.open_vocab_model = OwlViTForObjectDetection.from_pretrained(model_id)
            self.open_vocab_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            self.open_vocab_model.to(self.open_vocab_device).eval()
        except Exception as exc:
            self.open_vocab_error = f"{type(exc).__name__}: {exc}"
            self.open_vocab_model = None
            self.open_vocab_processor = None
            raise RuntimeError(
                "Open-vocabulary model could not be loaded. Install the optional "
                "transformers dependencies and allow the first model download. "
                f"Details: {self.open_vocab_error}"
            )

    def detect_open_vocabulary(self, frame_or_image_path, text_queries, threshold=0.12):
        """Detect objects described by user-supplied text labels (English prompts)."""
        frame = self._read_frame(frame_or_image_path)
        labels = [str(x).strip() for x in text_queries if str(x).strip()]
        if not labels:
            raise ValueError("Enter at least one object name, separated by commas.")
        self._load_open_vocabulary()
        from PIL import Image
        import torch
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb)
        # OWL-ViT expects one text list per image.
        inputs = self.open_vocab_processor(text=[labels], images=image, return_tensors="pt")
        inputs = {key: value.to(self.open_vocab_device) for key, value in inputs.items()}
        with torch.inference_mode():
            outputs = self.open_vocab_model(**inputs)
        target_sizes = torch.tensor([image.size[::-1]], device=self.open_vocab_device)
        processed = self.open_vocab_processor.post_process_object_detection(
            outputs=outputs, target_sizes=target_sizes, threshold=float(threshold)
        )[0]
        detections = []
        for score, label_idx, box in zip(processed["scores"], processed["labels"], processed["boxes"]):
            x1, y1, x2, y2 = [int(v) for v in box.tolist()]
            detections.append({
                "label": labels[int(label_idx)],
                "confidence": float(score.item()),
                "box": [x1, y1, x2, y2],
                "source": "OWL-ViT",
            })
        filtered = self._deduplicate(detections)
        return filtered, self._annotate(frame, filtered)
