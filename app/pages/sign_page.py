from pathlib import Path

from PySide6.QtCore import Signal, Qt, QThreadPool
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QFrame, QSizePolicy, QBoxLayout
)

from app.pages.common import page_header, panel
from app.widgets.camera_view import CameraView
from app.services.sign_service import SignLanguageService
from app.services.text_builder_service import TextBuilderService
from app.services.frame_worker import FrameTask


class SignPage(QWidget):
    speak_requested = Signal(str)
    stop_speech_requested = Signal()

    def __init__(self):
        super().__init__()
        self.service = None
        self.last_prediction = None
        self._frame_counter = 0
        self._uncertain_frames = 0
        self.text_builder = TextBuilderService()
        self.built_text = ""
        self.latest_hands = []
        self._frame_pool = QThreadPool(self)
        self._frame_pool.setMaxThreadCount(1)
        self._inference_busy = False
        self._active_task = None
        self._camera_generation = 0

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(16)
        outer.addWidget(page_header(
            "Arabic Sign Recognition",
            "Recognize supported Arabic static letters from a live hand pose or an uploaded ArASL-style image.",
            "ABILITYBRIDGE  /  AI MODULE 01"
        ))

        # Compact overview row.
        metrics = QHBoxLayout()
        metrics.setSpacing(12)
        self.metric_camera = self._metric_card("INPUT", "Camera / Image", "Choose your source")
        self.metric_hand = self._metric_card("LIVE HAND TRACKING", "One hand", "MediaPipe tracks 21 landmarks on the active hand")
        self.metric_model = self._metric_card("CLASSIFIER", "Loading…", "CNN · ArASL 32 classes")
        metrics.addWidget(self.metric_camera)
        metrics.addWidget(self.metric_hand)
        metrics.addWidget(self.metric_model)
        outer.addLayout(metrics)

        workspace = QHBoxLayout()
        workspace.setSpacing(16)
        self.workspace_layout = workspace
        self.metrics_layout = metrics

        # Left: live preview and controls.
        left = QVBoxLayout()
        left.setSpacing(10)
        camera_header = QHBoxLayout()
        camera_title = QLabel("LIVE CAMERA")
        camera_title.setObjectName("SectionTitle")
        self.camera_status = QLabel("● OFFLINE")
        self.camera_status.setObjectName("StatusPill")
        self.camera_status.setProperty("warning", True)
        camera_header.addWidget(camera_title)
        camera_header.addStretch()
        camera_header.addWidget(self.camera_status)
        left.addLayout(camera_header)

        self.camera = CameraView()
        self.camera.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        left.addWidget(self.camera, 1)

        controls = QHBoxLayout()
        controls.setSpacing(9)
        self.camera_controls_layout = controls
        self.btn_start = QPushButton("▶  Start camera")
        self.btn_stop = QPushButton("■  Stop")
        self.btn_stop.setObjectName("DangerButton")
        self.btn_stop.setEnabled(False)
        self.btn_upload = QPushButton("＋  Upload image")
        self.btn_upload.setObjectName("SecondaryButton")
        self.btn_recognize = QPushButton("Recognize image")
        self.btn_recognize.setObjectName("SecondaryButton")
        self.btn_recognize.setEnabled(False)
        controls.addWidget(self.btn_start, 2)
        controls.addWidget(self.btn_stop, 1)
        controls.addWidget(self.btn_upload, 2)
        controls.addWidget(self.btn_recognize, 2)
        left.addLayout(controls)
        workspace.addLayout(left, 7)

        # Right: result card and operational details.
        right = QVBoxLayout()
        right.setSpacing(12)

        result_panel = panel()
        result_layout = QVBoxLayout(result_panel)
        result_layout.setContentsMargins(20, 18, 20, 18)
        result_layout.setSpacing(8)

        result_head = QHBoxLayout()
        result_title = QLabel("RECOGNITION RESULT")
        result_title.setObjectName("BrandAccent")
        self.result_state = QLabel("WAITING")
        self.result_state.setObjectName("StatusPill")
        self.result_state.setProperty("warning", True)
        result_head.addWidget(result_title)
        result_head.addStretch()
        result_head.addWidget(self.result_state)
        result_layout.addLayout(result_head)

        self.result = QLabel("—")
        self.result.setAlignment(Qt.AlignCenter)
        self.result.setMinimumHeight(150)
        self.result.setObjectName("SignResult")
        result_layout.addWidget(self.result)

        self.confidence = QLabel("Confidence  ·  —")
        self.confidence.setObjectName("SectionTitle")
        result_layout.addWidget(self.confidence)

        self.confidence_hint = QLabel("The predicted letter will appear after the camera image is evaluated.")
        self.confidence_hint.setObjectName("Muted")
        self.confidence_hint.setWordWrap(True)
        result_layout.addWidget(self.confidence_hint)

        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet("color:#2a3a48;")
        result_layout.addWidget(divider)

        top_title = QLabel("TOP CANDIDATES")
        top_title.setObjectName("BrandAccent")
        result_layout.addWidget(top_title)
        self.top_candidates = QLabel("1   —\n2   —\n3   —")
        self.top_candidates.setObjectName("Muted")
        self.top_candidates.setWordWrap(True)
        result_layout.addWidget(self.top_candidates)

        built_title = QLabel("BUILT TEXT")
        built_title.setObjectName("BrandAccent")
        result_layout.addWidget(built_title)
        self.built_text_label = QLabel("—")
        self.built_text_label.setObjectName("SectionTitle")
        self.built_text_label.setWordWrap(True)
        self.built_text_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.built_text_label.setLayoutDirection(Qt.RightToLeft)
        result_layout.addWidget(self.built_text_label)
        text_controls = QHBoxLayout()
        self.text_controls_layout = text_controls
        self.btn_add_letter = QPushButton("＋ Add prediction")
        self.btn_add_letter.setObjectName("SecondaryButton")
        self.btn_space = QPushButton("Space")
        self.btn_space.setObjectName("SecondaryButton")
        self.btn_backspace = QPushButton("⌫")
        self.btn_backspace.setObjectName("SecondaryButton")
        self.btn_clear_text = QPushButton("Clear")
        self.btn_clear_text.setObjectName("SecondaryButton")
        text_controls.addWidget(self.btn_add_letter, 2)
        text_controls.addWidget(self.btn_space, 1)
        text_controls.addWidget(self.btn_backspace, 1)
        text_controls.addWidget(self.btn_clear_text, 1)
        result_layout.addLayout(text_controls)
        self.btn_read_text = QPushButton("🔊  Read built text aloud")
        self.btn_read_text.setObjectName("SecondaryButton")
        result_layout.addWidget(self.btn_read_text)
        voice_controls = QHBoxLayout()
        self.btn_read_letter = QPushButton("Read current letter")
        self.btn_read_letter.setObjectName("SecondaryButton")
        self.btn_test_voice = QPushButton("Test Arabic voice")
        self.btn_test_voice.setObjectName("SecondaryButton")
        self.btn_stop_voice = QPushButton("Stop speech")
        self.btn_stop_voice.setObjectName("SecondaryButton")
        voice_controls.addWidget(self.btn_read_letter)
        voice_controls.addWidget(self.btn_test_voice)
        voice_controls.addWidget(self.btn_stop_voice)
        result_layout.addLayout(voice_controls)
        right.addWidget(result_panel)

        status_panel = panel()
        status_layout = QVBoxLayout(status_panel)
        status_layout.setContentsMargins(18, 16, 18, 16)
        status_layout.setSpacing(8)
        status_title = QLabel("SYSTEM STATUS")
        status_title.setObjectName("BrandAccent")
        status_layout.addWidget(status_title)
        self.status = QLabel("Loading Arabic sign CNN…")
        self.status.setObjectName("Muted")
        self.status.setWordWrap(True)
        status_layout.addWidget(self.status)
        self.model_path_label = QLabel(
            "Classifier: models/cnn_baseline/best_cnn_model.pth\n"
            "CNN · grayscale 64×64 · MediaPipe hand ROI"
        )
        self.model_path_label.setObjectName("Muted")
        self.model_path_label.setWordWrap(True)
        status_layout.addWidget(self.model_path_label)
        right.addWidget(status_panel)
        right.addStretch(1)
        workspace.addLayout(right, 4)
        outer.addLayout(workspace, 1)

        self.btn_start.clicked.connect(self.start_camera)
        self.btn_stop.clicked.connect(self.camera.stop_camera)
        self.btn_upload.clicked.connect(self.load_image)
        self.btn_recognize.clicked.connect(self.predict_still_image)
        self.btn_add_letter.clicked.connect(self.append_prediction)
        self.btn_space.clicked.connect(self.append_space)
        self.btn_read_text.clicked.connect(self.read_built_text)
        self.btn_test_voice.clicked.connect(self.test_arabic_voice)
        self.btn_read_letter.clicked.connect(self.read_current_letter)
        self.btn_stop_voice.clicked.connect(self.stop_speech_requested.emit)
        self.btn_backspace.clicked.connect(self.remove_last_character)
        self.btn_clear_text.clicked.connect(self.clear_built_text)
        self.camera.camera_state_changed.connect(self.on_camera_state)
        self.camera.frame_updated.connect(self.process_live_frame)

        self.initialize_service()

    def _metric_card(self, eyebrow, value, caption):
        card = panel("MetricPanel")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(15, 12, 15, 12)
        layout.setSpacing(3)
        top = QLabel(eyebrow)
        top.setObjectName("BrandAccent")
        main = QLabel(value)
        main.setObjectName("SectionTitle")
        sub = QLabel(caption)
        sub.setObjectName("Muted")
        sub.setWordWrap(True)
        layout.addWidget(top)
        layout.addWidget(main)
        layout.addWidget(sub)
        card.value_label = main
        return card

    def initialize_service(self):
        try:
            self.service = SignLanguageService(num_hands=1)
            model_ready = self.service.model is not None
            hand_ready = self.service.landmarker is not None
            self.metric_model.value_label.setText(
                f"{len(self.service.class_names)} classes" if model_ready else "CNN unavailable"
            )
            self.metric_hand.value_label.setText(
                "One hand" if hand_ready else "MediaPipe unavailable"
            )
            self.btn_recognize.setEnabled(model_ready)
            parts = []
            parts.append(
                f"CNN ready on {self.service.device.upper()} · 32 ArASL classes."
                if model_ready else
                "CNN unavailable: " + (self.service.load_error or "model could not be loaded.")
            )
            parts.append(
                "MediaPipe ready: tracking one hand. Hold a clear static sign until the prediction stabilizes."
                if hand_ready else
                "MediaPipe unavailable: " + (self.service.hand_error or "hand detector could not be loaded.")
            )
            self.status.setText(" ".join(parts))
            ready = model_ready and hand_ready
            self.result_state.setText("LIVE READY" if ready else "SETUP REQUIRED")
            self.result_state.setProperty("warning", not ready)
            self.result_state.style().unpolish(self.result_state)
            self.result_state.style().polish(self.result_state)
        except Exception as exc:
            self.service = None
            self.status.setText(f"Sign recognition initialization failed: {type(exc).__name__}: {exc}")
            self.metric_model.value_label.setText("Unavailable")
            self.metric_hand.value_label.setText("Unavailable")
            self.btn_recognize.setEnabled(False)
            self.result_state.setText("SETUP REQUIRED")
            self.result_state.setProperty("warning", True)
            self.result_state.style().unpolish(self.result_state)
            self.result_state.style().polish(self.result_state)

    def set_confidence_threshold(self, value):
        if self.service is not None:
            self.service.min_live_confidence = max(0.10, min(0.95, float(value)))

    def start_camera(self):
        started = self.camera.start_camera()
        if started:
            self.latest_hands = []
            self.reset_result()
            if self.service:
                self.service.reset_smoothing()
            self.metric_camera.value_label.setText("Live camera")
            if not self.service or not self.service.model or not self.service.landmarker:
                self.status.setText("Camera preview is running, but the CNN model or MediaPipe is unavailable. Check System Status.")
            else:
                self.status.setText("Camera running. Show a supported Arabic letter with either hand. Small pose variations are tolerated; hold briefly for a stable result.")
        else:
            self.status.setText("Camera could not be opened. Check permissions or close other apps using it.")

    def load_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose a sign image", "",
            "Image files (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if not path:
            return
        if self.camera.capture is not None:
            self.camera.stop_camera()
        if self.camera.load_image(path):
            self.latest_hands = []
            self.metric_camera.value_label.setText(Path(path).name)
            self.btn_recognize.setEnabled(bool(self.service and self.service.model is not None))
            self.status.setText(
                "Image loaded. The CNN model is not available."
                if not self.service or self.service.model is None
                else "Image loaded. Run recognition to classify the hand sign."
            )
            self.reset_result()

    def predict_still_image(self):
        if self.service is None:
            self.status.setText("Image loaded, but the CNN model is unavailable. Check models/cnn_baseline/best_cnn_model.pth.")
            return
        if self.service.model is None:
            self.status.setText("The CNN classifier is not loaded. Check the CNN checkpoint and run setup_windows.bat.")
            return
        if self.camera.current_frame is None:
            self.status.setText("Upload an image first.")
            return
        try:
            prediction = self.service.predict(self.camera.current_frame)
            self.display_prediction(prediction)
            self.status.setText("Still-image recognition completed. Check the confidence and top candidates when the result is uncertain.")
        except Exception as exc:
            self.status.setText(f"Image recognition failed: {exc}")

    def process_live_frame(self, frame):
        if self.service is None or self.service.landmarker is None or self.service.model is None:
            return
        self._frame_counter += 1
        if self._frame_counter % 2 or self._inference_busy:
            return
        self._inference_busy = True
        task = FrameTask(self.service.process_frame, frame.copy(), self._camera_generation)
        self._active_task = task
        task.signals.finished.connect(self._on_live_inference_finished)
        task.signals.failed.connect(self._on_live_inference_failed)
        self._frame_pool.start(task)

    def _on_live_inference_finished(self, output, generation):
        self._inference_busy = False
        self._active_task = None
        if generation != self._camera_generation or self.camera.capture is None:
            return
        try:
            hands = output.get("hands", [])
            self.latest_hands = hands
            self.camera.set_hand_overlays(hands)
            if not hands:
                self._uncertain_frames += 1
                self.reset_result(keep_state=True)
                self.result_state.setText("NO HAND")
                self.result_state.setProperty("warning", True)
                self.result_state.style().unpolish(self.result_state)
                self.result_state.style().polish(self.result_state)
                self.status.setText(output.get("error") or "No hand detected.")
                return
            valid = [h for h in hands if h.get("accepted") and h.get("label")]
            if not valid:
                preview = [h for h in hands if h.get("candidate_label")]
                if preview:
                    self.result.setText(" · ".join(h.get("candidate_label", "—") for h in preview))
                    self.confidence.setText(" · ".join(
                        f'Hand {h.get("hand_number", i + 1)}: {h.get("confidence", 0):.1%}'
                        for i, h in enumerate(preview)
                    ))
                    self.top_candidates.setText("\n".join(
                        f'Hand {h.get("hand_number", i + 1)}\n' +
                        "\n".join(f'  {n}. {c["label"]}  {c["confidence"]:.1%}'
                                   for n, c in enumerate(h.get("top3", []), 1))
                        for i, h in enumerate(preview)
                    ))
                    self.result_state.setText("HOLD POSE")
                    self.result_state.setProperty("warning", True)
                    self.result_state.style().unpolish(self.result_state)
                    self.result_state.style().polish(self.result_state)
                    self.confidence_hint.setText(
                        "Keep the sign steady for a moment. Recent predictions are combined to tolerate small pose variations."
                    )
                    self.status.setText("Hand detected. Waiting for a stable result; uncertain guesses are not added to the text.")
                else:
                    self.result_state.setText("HAND DETECTED")
                    self.result_state.setProperty("warning", True)
                    self.result_state.style().unpolish(self.result_state)
                    self.result_state.style().polish(self.result_state)
                    self.status.setText("Hand detected, but classification is unavailable: " +
                                        "; ".join(h.get("error", "unknown error") for h in hands))
                return
            labels = [h["label"] for h in valid]
            self.result.setText("  |  ".join(labels))
            self.confidence.setText(" · ".join(
                f'Hand {h.get("hand_number", i + 1)}: {h.get("confidence", 0):.1%}'
                for i, h in enumerate(valid)
            ))
            self.confidence_hint.setText(
                "Each detected hand is classified independently. Confidence is a model score, not a guarantee of correctness."
            )
            self.result_state.setText(f"{len(valid)} HAND(S) · LIVE")
            self.result_state.setProperty("warning", False)
            self.result_state.style().unpolish(self.result_state)
            self.result_state.style().polish(self.result_state)
            rows = []
            for h_index, hand in enumerate(valid, 1):
                rows.append(f'Hand {hand.get("hand_number", h_index)} — {hand["label"]} (stable)')
                for rank, item in enumerate(hand.get("top3", []), 1):
                    rows.append(f'  {rank}. {item["label"]}  {item["confidence"]:.1%}')
            self.top_candidates.setText("\n".join(rows))
            self.status.setText(f"Live recognition active · {len(valid)} hand(s) detected.")
        except Exception as exc:
            self.latest_hands = []
            self.camera.set_hand_overlays([])
            self.status.setText(f"Live recognition error: {type(exc).__name__}: {exc}")

    def _on_live_inference_failed(self, message, generation):
        self._inference_busy = False
        self._active_task = None
        if generation == self._camera_generation:
            self.status.setText(f"Live recognition error: {message}")

    def display_prediction(self, prediction):
        self.last_prediction = prediction
        accepted = prediction.get("accepted", True)
        self.result.setText(prediction.get("label", "—"))
        self.confidence.setText(f'Confidence  ·  {prediction.get("confidence", 0):.1%}')
        self.confidence_hint.setText(
            f'Stable across {prediction.get("stable_frames", "—")} frames · '
            f'agreement {prediction.get("agreement", 1.0):.0%}'
            if prediction.get("stable_frames") is not None
            else ("Single-image prediction" if accepted else "Low confidence or close competing classes; do not add this letter yet.")
        )
        self.result_state.setText("SIGN DETECTED" if accepted else "UNCERTAIN")
        self.result_state.setProperty("warning", not accepted)
        self.result_state.style().unpolish(self.result_state)
        self.result_state.style().polish(self.result_state)
        rows = []
        for i, item in enumerate(prediction.get("top3", []), 1):
            rows.append(f'{i}.  {item.get("label", "?")}     {item.get("confidence", 0):.1%}')
        self.top_candidates.setText("\n".join(rows) if rows else "No candidate scores available.")

    def append_prediction(self):
        if not self.latest_hands:
            if self.last_prediction and self.last_prediction.get("accepted", False):
                letter = self.last_prediction.get("label", "")
            else:
                self.status.setText("لا يوجد حرف موثوق لإضافته. انتظر نتيجة مستقرة أولاً.")
                return
        else:
            # One Add action adds one selected prediction, not two simultaneous hands.
            # The ArASL image classifier is trained for one static hand pose.
            candidates = [h for h in self.latest_hands if h.get("accepted") and h.get("label")]
            if candidates:
                letter = max(candidates, key=lambda h: h.get("confidence", 0.0)).get("label", "")
            else:
                letter = ""
        if not letter:
            self.status.setText("No recognized letter is available to add.")
            return
        self.built_text = self.text_builder.add_text(letter)
        self.built_text_label.setText(self.built_text)

    def append_space(self):
        self.built_text = self.text_builder.add_space()
        self.built_text_label.setText(self.built_text or "—")

    def read_current_letter(self):
        letter = ""
        if self.latest_hands:
            accepted = [h for h in self.latest_hands if h.get("accepted") and h.get("label")]
            if accepted:
                letter = max(accepted, key=lambda h: h.get("confidence", 0.0))["label"]
        elif self.last_prediction and self.last_prediction.get("accepted", True):
            letter = self.last_prediction.get("label", "")
        if not letter:
            self.status.setText("لا يوجد حرف ثابت لقراءته حالياً.")
            return
        self.speak_requested.emit(letter)
        self.status.setText(f"جاري نطق الحرف: {letter}")

    def test_arabic_voice(self):
        self.speak_requested.emit("مرحباً، هذا اختبار الصوت العربي في تطبيق أبيليتي بريدج.")
        self.status.setText("جاري اختبار الصوت العربي...")

    def read_built_text(self):
        text = self.built_text.strip()
        if not text:
            self.status.setText("Build some text before requesting speech.")
            return
        self.status.setText("جاري تجهيز قراءة النص...")
        self.speak_requested.emit(text)

    def on_speech_status(self, message):
        self.status.setText(str(message))

    def remove_last_character(self):
        self.built_text = self.text_builder.backspace()
        self.built_text_label.setText(self.built_text or "—")

    def clear_built_text(self):
        self.built_text = self.text_builder.clear()
        self.built_text_label.setText("—")
        self.status.setText("Built text cleared.")

    def reset_result(self, keep_state=False):
        self.last_prediction = None
        self.result.setText("—")
        self.confidence.setText("Confidence  ·  —")
        self.confidence_hint.setText("Waiting for a stable sign.")
        self.top_candidates.setText("1   —\n2   —\n3   —")
        if not keep_state:
            self.result_state.setText("WAITING")
            self.result_state.setProperty("warning", True)
            self.result_state.style().unpolish(self.result_state)
            self.result_state.style().polish(self.result_state)

    def on_camera_state(self, running):
        self._camera_generation += 1
        self.btn_start.setEnabled(not running)
        self.btn_stop.setEnabled(running)
        if not running:
            self.metric_camera.value_label.setText("Camera / Image")
            self.latest_hands = []
            self.camera.set_hand_overlays([])
            if self.service:
                self.service.reset_smoothing()

    def resizeEvent(self, event):
        width = self.width()
        compact = width < 980
        narrow = width < 720
        self.workspace_layout.setDirection(
            QBoxLayout.TopToBottom if compact else QBoxLayout.LeftToRight
        )
        self.metrics_layout.setDirection(
            QBoxLayout.TopToBottom if narrow else QBoxLayout.LeftToRight
        )
        self.camera_controls_layout.setDirection(
            QBoxLayout.TopToBottom if narrow else QBoxLayout.LeftToRight
        )
        self.text_controls_layout.setDirection(
            QBoxLayout.TopToBottom if width < 620 else QBoxLayout.LeftToRight
        )
        self.result.setMinimumHeight(112 if narrow else 150)
        super().resizeEvent(event)

    def shutdown(self):
        self.camera.stop_camera()
        self._frame_pool.waitForDone()
        if self.service is not None:
            self.service.close()
            self.service = None

    def closeEvent(self, event):
        self.shutdown()
        super().closeEvent(event)
