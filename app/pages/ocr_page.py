from pathlib import Path

from PySide6.QtCore import Signal, QThreadPool
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog,
    QTextEdit, QFrame
)

from app.pages.common import page_header, panel
from app.services.ocr_service import OCRService
from app.widgets.camera_view import CameraView
from app.services.frame_worker import FrameTask


class OCRPage(QWidget):
    speak_requested = Signal(str)
    stop_speech_requested = Signal()

    def __init__(self):
        super().__init__()
        self.service = OCRService(languages=("ar", "en"))
        self.current_image = None
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)
        self._task = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addWidget(page_header(
            "OCR Assistant",
            "Extract printed Arabic and English text from an image or a camera capture, then read it aloud.",
            "ABILITYBRIDGE  /  AI MODULE 03"
        ))

        body = QHBoxLayout()
        body.setSpacing(16)
        left = QVBoxLayout()
        left.addWidget(QLabel("IMAGE / CAMERA INPUT"))
        self.camera = CameraView()
        left.addWidget(self.camera, 1)
        controls = QHBoxLayout()
        self.btn_start = QPushButton("▶ Start camera")
        self.btn_stop = QPushButton("■ Stop")
        self.btn_stop.setObjectName("DangerButton")
        self.btn_stop.setEnabled(False)
        self.btn_upload = QPushButton("＋ Upload image")
        self.btn_upload.setObjectName("SecondaryButton")
        self.btn_capture = QPushButton("Capture current frame")
        self.btn_capture.setObjectName("SecondaryButton")
        controls.addWidget(self.btn_start)
        controls.addWidget(self.btn_stop)
        controls.addWidget(self.btn_upload)
        controls.addWidget(self.btn_capture)
        left.addLayout(controls)
        body.addLayout(left, 6)

        right_panel = panel()
        right = QVBoxLayout(right_panel)
        right.setContentsMargins(18, 18, 18, 18)
        right.setSpacing(10)
        heading = QLabel("EXTRACTED TEXT")
        heading.setObjectName("BrandAccent")
        right.addWidget(heading)
        self.results = QTextEdit()
        self.results.setPlaceholderText("Extracted Arabic and English text will appear here…")
        right.addWidget(self.results, 1)
        self.status = QLabel("Upload an image or capture a camera frame to begin. First OCR run downloads pretrained Arabic/English model weights.")
        self.status.setObjectName("Muted")
        self.status.setWordWrap(True)
        right.addWidget(self.status)
        self.btn_run = QPushButton("Extract text (OCR)")
        self.btn_run.setObjectName("PrimaryButton")
        self.btn_read = QPushButton("🔊 Read extracted text")
        self.btn_read.setObjectName("SecondaryButton")
        self.btn_stop_audio = QPushButton("Stop speech")
        self.btn_stop_audio.setObjectName("SecondaryButton")
        right.addWidget(self.btn_run)
        right.addWidget(self.btn_read)
        right.addWidget(self.btn_stop_audio)
        body.addWidget(right_panel, 5)
        layout.addLayout(body, 1)

        self.btn_start.clicked.connect(self.start_camera)
        self.btn_stop.clicked.connect(self.camera.stop_camera)
        self.btn_upload.clicked.connect(self.upload_image)
        self.btn_capture.clicked.connect(self.capture_frame)
        self.btn_run.clicked.connect(self.run_ocr)
        self.btn_read.clicked.connect(self.read_text)
        self.btn_stop_audio.clicked.connect(self.stop_speech_requested.emit)
        self.camera.camera_state_changed.connect(self.on_camera_state)

    def start_camera(self):
        if self.camera.start_camera():
            self.status.setText("Camera is running. Capture a frame, then extract text.")
        else:
            self.status.setText("Could not open camera. Check Windows camera permissions.")

    def on_camera_state(self, running):
        self.btn_start.setEnabled(not running)
        self.btn_stop.setEnabled(running)

    def upload_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose image", "", "Images (*.png *.jpg *.jpeg *.bmp *.webp)")
        if not path:
            return
        if self.camera.capture is not None:
            self.camera.stop_camera()
        if self.camera.load_image(path):
            self.current_image = path
            self.status.setText(f"Image loaded: {Path(path).name}. Press Extract text.")

    def capture_frame(self):
        frame = self.camera.current_frame
        if frame is None:
            self.status.setText("Start the camera or upload an image first.")
            return
        self.current_image = frame.copy()
        self.status.setText("Camera frame captured. Press Extract text.")

    def run_ocr(self):
        if self.current_image is None:
            if self.camera.current_frame is not None:
                self.current_image = self.camera.current_frame.copy()
            else:
                self.status.setText("Upload an image or capture a camera frame first.")
                return
        self.btn_run.setEnabled(False)
        self.status.setText("Loading OCR model / extracting text. The first run may take longer…")
        image_input = self.current_image.copy() if hasattr(self.current_image, "copy") else self.current_image
        task = FrameTask(self.service.read, image_input, 0)
        self._task = task
        task.signals.finished.connect(self._on_ocr_finished)
        task.signals.failed.connect(self._on_ocr_failed)
        self._pool.start(task)

    def _on_ocr_finished(self, lines, _generation):
        self._task = None
        self.btn_run.setEnabled(True)
        if not lines:
            self.results.setPlainText("No readable printed text was found.")
            self.status.setText("OCR finished, but no text was detected. Try a clearer, well-lit image.")
            return
        rendered = "\n".join(f'{item["text"]}   ({item["confidence"]:.0%})' for item in lines)
        self.results.setPlainText(rendered)
        self.status.setText(f"OCR completed · {len(lines)} text segment(s) detected.")

    def _on_ocr_failed(self, message, _generation):
        self._task = None
        self.btn_run.setEnabled(True)
        self.status.setText(f"OCR failed: {message}")

    def read_text(self):
        text = " ".join(line.strip() for line in self.results.toPlainText().splitlines() if line.strip())
        # Remove confidence values from the speech string.
        import re
        text = re.sub(r"\s+\(\d+%\)", "", text).strip()
        if not text:
            self.status.setText("Extract text before requesting speech.")
            return
        self.speak_requested.emit(text)

    def shutdown(self):
        self.camera.stop_camera()
        self._pool.waitForDone()
