from PySide6.QtCore import Signal, QThreadPool
import time
import time
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QTextEdit, QLineEdit, QBoxLayout
)
from app.pages.common import page_header, panel
from app.widgets.camera_view import CameraView
from app.services.vision_service import VisionService
from app.services.tts_service import TTSService
from app.services.frame_worker import FrameTask


class VisionPage(QWidget):
    speak_requested = Signal(str)

    def __init__(self):
        super().__init__()
        self.service = VisionService()
        self.tts = TTSService()
        self._frame_counter = 0
        self.last_description = ""
        self._last_spoken_signature = None
        self._last_auto_speech_at = 0.0
        self._last_detection_count = 0
        self._frame_pool = QThreadPool(self)
        self._frame_pool.setMaxThreadCount(1)
        self._inference_busy = False
        self._active_task = None
        self._camera_generation = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addWidget(page_header(
            "Vision Assistant",
            "Detect everyday objects in a live scene or uploaded photo, then read the results aloud.",
            "ABILITYBRIDGE  /  AI MODULE 02"
        ))

        body = QHBoxLayout()
        body.setSpacing(16)
        self.body_layout = body
        left = QVBoxLayout()
        left.setSpacing(10)
        head = QHBoxLayout()
        label = QLabel("SCENE PREVIEW")
        label.setObjectName("SectionTitle")
        self.camera_status = QLabel("● OFFLINE")
        self.camera_status.setObjectName("StatusPill")
        self.camera_status.setProperty("warning", True)
        head.addWidget(label)
        head.addStretch()
        head.addWidget(self.camera_status)
        left.addLayout(head)
        self.camera = CameraView()
        left.addWidget(self.camera, 1)

        controls = QHBoxLayout()
        self.controls_layout = controls
        self.btn_start = QPushButton("▶  Start camera")
        self.btn_stop = QPushButton("■  Stop")
        self.btn_stop.setObjectName("DangerButton")
        self.btn_stop.setEnabled(False)
        self.btn_image = QPushButton("＋  Upload image")
        self.btn_image.setObjectName("SecondaryButton")
        self.btn_detect = QPushButton("Run detection")
        self.btn_detect.setObjectName("SecondaryButton")
        controls.addWidget(self.btn_start, 2)
        controls.addWidget(self.btn_stop, 1)
        controls.addWidget(self.btn_image, 2)
        controls.addWidget(self.btn_detect, 2)
        left.addLayout(controls)
        body.addLayout(left, 7)

        right = panel()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(18, 18, 18, 18)
        right_layout.setSpacing(10)
        title = QLabel("OBJECTS IN VIEW")
        title.setObjectName("BrandAccent")
        right_layout.addWidget(title)
        self.prompt_input = QLineEdit()
        self.prompt_input.setPlaceholderText("Optional: phone, wallet, glasses, medicine box, remote control…")
        right_layout.addWidget(self.prompt_input)
        self.btn_prompt_detect = QPushButton("Search named objects (open vocabulary)")
        self.btn_prompt_detect.setObjectName("SecondaryButton")
        right_layout.addWidget(self.btn_prompt_detect)
        self.results = QTextEdit()
        self.results.setReadOnly(True)
        self.results.setPlaceholderText("Detected objects and confidence scores will appear here.")
        right_layout.addWidget(self.results, 1)
        self.status = QLabel("Loading YOLO object detector…")
        self.status.setObjectName("Muted")
        self.status.setWordWrap(True)
        right_layout.addWidget(self.status)
        self.btn_speak = QPushButton("🔊  Read results aloud")
        self.btn_stop_audio = QPushButton("Stop speech")
        self.btn_stop_audio.setObjectName("SecondaryButton")
        self.btn_test_voice = QPushButton("Test Arabic voice")
        self.btn_test_voice.setObjectName("SecondaryButton")
        right_layout.addWidget(self.btn_speak)
        right_layout.addWidget(self.btn_test_voice)
        right_layout.addWidget(self.btn_stop_audio)
        body.addWidget(right, 4)
        layout.addLayout(body, 1)

        if self.service.model is None:
            self.status.setText(
                "YOLO could not be initialized. Check the installed dependencies and confirm that the "
                f"bundled yolo11n.pt file exists. Details: {self.service.error}"
            )
            self.btn_detect.setEnabled(False)
        else:
            self.status.setText(
                f"YOLO ready · multi-object mode · {self.service.weights_path}. "
                "The bundled model recognizes common COCO categories; it cannot identify arbitrary objects outside those classes."
            )

        self.btn_start.clicked.connect(self.start_camera)
        self.btn_stop.clicked.connect(self.camera.stop_camera)
        self.btn_image.clicked.connect(self.load_image)
        self.btn_detect.clicked.connect(self.detect_current)
        self.btn_prompt_detect.clicked.connect(self.detect_prompted_objects)
        self.btn_speak.clicked.connect(self.speak_description)
        self.btn_test_voice.clicked.connect(lambda: self.tts.speak("مرحباً، هذا اختبار الصوت العربي في مساعد الرؤية."))
        self.btn_stop_audio.clicked.connect(self.tts.stop)
        self.tts.status_changed.connect(self.on_tts_status)
        self.camera.camera_state_changed.connect(self.on_camera_state)
        self.camera.frame_updated.connect(self.process_live_frame)

    def resizeEvent(self, event):
        compact = self.width() < 980
        narrow = self.width() < 720
        self.body_layout.setDirection(
            QBoxLayout.TopToBottom if compact else QBoxLayout.LeftToRight
        )
        self.controls_layout.setDirection(
            QBoxLayout.TopToBottom if narrow else QBoxLayout.LeftToRight
        )
        super().resizeEvent(event)

    def start_camera(self):
        started = self.camera.start_camera()
        if started:
            self.status.setText("Camera running. Object detection and Arabic scene narration are automatic.")
        else:
            self.status.setText("Camera could not be opened. Check Windows camera permission and close other apps using it.")
        return started

    def load_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select scene image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if not path:
            return
        if self.camera.capture is not None:
            self.camera.stop_camera()
        if self.camera.load_image(path):
            self.status.setText("Image loaded. Press Run detection.")
            self.detect_current()

    def detect_current(self):
        if self.service.model is None:
            self.status.setText(f"YOLO is unavailable: {self.service.error}")
            return
        frame = self.camera.current_frame
        if frame is None:
            self.status.setText("Start the camera or upload an image first.")
            return
        try:
            detections, annotated = self.service.detect(frame)
            self.camera.set_object_overlays(detections)
            self.show_detections(detections)
            self.status.setText(f"Detection complete · {len(detections)} object(s) found.")
        except Exception as exc:
            self.status.setText(f"Detection failed: {exc}")

    def detect_prompted_objects(self):
        frame = self.camera.current_frame
        if frame is None:
            self.status.setText("Start the camera or upload an image first.")
            return
        raw = self.prompt_input.text().strip()
        labels = [item.strip() for item in raw.split(",") if item.strip()]
        if not labels:
            self.status.setText("Enter object names in English, separated by commas.")
            return
        self.status.setText("Loading open-vocabulary model or searching for the requested objects…")
        try:
            detections, annotated = self.service.detect_open_vocabulary(frame, labels)
            self.camera.set_object_overlays(detections)
            self.show_detections(detections)
            self.status.setText(
                f"Open-vocabulary search complete · {len(detections)} match(es). "
                "This model searches for the object names you entered; it does not know every object automatically."
            )
        except Exception as exc:
            self.status.setText(f"Open-vocabulary detection failed: {exc}")

    def process_live_frame(self, frame):
        if self.service.model is None:
            return
        self._frame_counter += 1
        if self._frame_counter % 5 or self._inference_busy:
            return
        self._inference_busy = True
        task = FrameTask(self.service.detect, frame.copy(), self._camera_generation)
        self._active_task = task
        task.signals.finished.connect(self._on_live_detection_finished)
        task.signals.failed.connect(self._on_live_detection_failed)
        self._frame_pool.start(task)

    def _on_live_detection_finished(self, result, generation):
        self._inference_busy = False
        self._active_task = None
        if generation != self._camera_generation or self.camera.capture is None:
            return
        detections, _annotated = result
        self.camera.set_object_overlays(detections)
        self.show_detections(detections)
        self._maybe_auto_speak(detections)
        self.status.setText(f"Live detection · {len(detections)} object(s) found.")

    def _on_live_detection_failed(self, message, generation):
        self._inference_busy = False
        self._active_task = None
        if generation == self._camera_generation:
            self.status.setText(f"Live detection error: {message}")

    def show_detections(self, detections):
        """Render detections and prepare a natural Arabic, names-only summary."""
        if not detections:
            self.results.setPlainText("No recognizable objects were found in this scene.")
            self.last_description = "لم أتمكن من التعرف على أشياء واضحة في المشهد."
            return

        arabic_names = {
            "person": "شخص", "bicycle": "دراجة", "car": "سيارة", "motorcycle": "دراجة نارية",
            "sports ball": "كرة رياضية", "frisbee": "قرص طائر", "skis": "زلاجات",
            "snowboard": "لوح تزلج على الثلج", "kite": "طائرة ورقية",
            "baseball bat": "مضرب بيسبول", "baseball glove": "قفاز بيسبول",
            "skateboard": "لوح تزلج", "surfboard": "لوح ركوب الأمواج",
            "tennis racket": "مضرب تنس", "parking meter": "عداد انتظار السيارات",
            "airplane": "طائرة", "bus": "أتوبيس", "train": "قطار", "truck": "شاحنة",
            "boat": "قارب", "traffic light": "إشارة مرور", "fire hydrant": "صنبور إطفاء",
            "stop sign": "علامة توقف", "bench": "مقعد", "bird": "طائر", "cat": "قطة",
            "dog": "كلب", "horse": "حصان", "sheep": "خروف", "cow": "بقرة",
            "elephant": "فيل", "bear": "دب", "zebra": "حمار وحشي", "giraffe": "زرافة",
            "backpack": "حقيبة ظهر", "umbrella": "مظلة", "handbag": "حقيبة يد",
            "sports ball": "كرة رياضية",
            "tie": "رابطة عنق", "suitcase": "حقيبة سفر", "bottle": "زجاجة",
            "wine glass": "كأس", "cup": "كوب", "fork": "شوكة", "knife": "سكين",
            "spoon": "ملعقة", "bowl": "وعاء", "banana": "موزة", "apple": "تفاحة",
            "sandwich": "شطيرة", "orange": "برتقالة", "broccoli": "بروكلي",
            "carrot": "جزرة", "hot dog": "هوت دوج", "pizza": "بيتزا",
            "donut": "دونات", "cake": "كعكة", "chair": "كرسي", "couch": "أريكة",
            "potted plant": "نبات في أصيص", "bed": "سرير", "dining table": "طاولة طعام",
            "toilet": "مرحاض", "tv": "تلفاز", "laptop": "حاسوب محمول",
            "mouse": "فأرة", "remote": "جهاز تحكم", "keyboard": "لوحة مفاتيح",
            "cell phone": "هاتف محمول", "microwave": "ميكروويف", "oven": "فرن",
            "toaster": "محمصة", "sink": "حوض", "refrigerator": "ثلاجة",
            "book": "كتاب", "clock": "ساعة", "vase": "مزهرية", "scissors": "مقص",
            "teddy bear": "دبدوب", "hair drier": "مجفف شعر", "toothbrush": "فرشاة أسنان",
            "wallet": "محفظة", "eyeglasses": "نظارة", "glasses": "نظارة",
            "medicine box": "علبة دواء", "remote control": "ريموت كنترول",
            "keys": "مفاتيح", "key": "مفتاح", "watch": "ساعة يد",
            "tablet": "جهاز لوحي", "charger": "شاحن", "headphones": "سماعة رأس",
            "earbuds": "سماعات أذن", "power bank": "بطارية متنقلة",
            "computer monitor": "شاشة كمبيوتر", "monitor": "شاشة",
        }
        rows = []
        spoken_names = []
        seen = set()
        for item in detections:
            raw_name = str(item.get("label", "object")).strip()
            key = raw_name.casefold()
            arabic = arabic_names.get(key, raw_name)
            confidence = float(item.get("confidence", 0.0))
            rows.append(f"• {arabic}  —  {confidence:.0%}")
            if key not in seen:
                seen.add(key)
                spoken_names.append(arabic)

        self.results.setPlainText("الأشياء التي تم التعرف عليها:\n" + "\n".join(rows))
        # Speech deliberately names objects; it does not read counts, scores or coordinates.
        if len(spoken_names) == 1:
            self.last_description = f"أرى أمامك {spoken_names[0]}."
        else:
            self.last_description = "أرى أمامك: " + "، ".join(spoken_names[:12]) + "."


    def _maybe_auto_speak(self, detections):
        """Speak only when the set of recognized object types changes."""
        names = sorted({str(item.get("label", "")).strip().casefold() for item in detections if item.get("label")})
        if not names:
            return
        signature = tuple(names)
        now = time.monotonic()
        if signature == self._last_spoken_signature or now - self._last_auto_speech_at < 2.5:
            return
        text = self.last_description.strip()
        if text:
            self._last_spoken_signature = signature
            self._last_auto_speech_at = now
            self.tts.speak(text)

    def speak_description(self):
        # Do not fall back to the raw detection table: it contains confidence
        # percentages and bounding-box coordinates, which are not a scene description.
        text = self.last_description.strip()
        if not text:
            self.status.setText("Run object detection before requesting speech.")
            return
        self.tts.speak(text)



    def on_tts_status(self, message):
        self.status.setText(message)

    def on_camera_state(self, running):
        self._camera_generation += 1
        self.btn_start.setEnabled(not running)
        self.btn_stop.setEnabled(running)
        self.camera_status.setText("● LIVE" if running else "● OFFLINE")
        self.camera_status.setProperty("warning", not running)
        self.camera_status.style().unpolish(self.camera_status)
        self.camera_status.style().polish(self.camera_status)
        if not running:
            self.status.setText("Camera stopped.")

    def shutdown(self):
        self.camera.stop_camera()
        self._frame_pool.waitForDone()
        self.tts.close()
