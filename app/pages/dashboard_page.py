from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton

from app.pages.common import page_header, panel


class DashboardPage(QWidget):
    open_sign = Signal()
    open_vision = Signal()
    open_ocr = Signal()
    open_settings = Signal()

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)
        layout.addWidget(page_header(
            "Welcome to AbilityBridge AI",
            "Arabic sign recognition, live scene narration, printed-text OCR, and spoken assistance.",
            "YOUR ACCESSIBILITY WORKSPACE"
        ))

        status_row = QHBoxLayout()
        status_row.setSpacing(12)
        self.sign_status = self._status_card("ARABIC SIGN MODEL", "Checking…", "32 ArASL sign classes")
        self.vision_status = self._status_card("VISION MODEL", "Checking…", "YOLO11n object detection")
        self.speech_status = self._status_card("VOICE ASSISTANCE", "Windows voice", "Arabic voice recommended")
        status_row.addWidget(self.sign_status)
        status_row.addWidget(self.vision_status)
        status_row.addWidget(self.speech_status)
        layout.addLayout(status_row)

        quick = panel()
        quick_layout = QVBoxLayout(quick)
        quick_layout.setContentsMargins(22, 22, 22, 22)
        quick_layout.setSpacing(12)
        heading = QLabel("QUICK ACCESS")
        heading.setObjectName("BrandAccent")
        quick_layout.addWidget(heading)
        row = QHBoxLayout()
        self.sign_button = QPushButton("Open Sign Recognition")
        self.sign_button.setMinimumHeight(54)
        self.vision_button = QPushButton("Open Vision Assistant")
        self.vision_button.setObjectName("SecondaryButton")
        self.vision_button.setMinimumHeight(54)
        self.ocr_button = QPushButton("Open OCR Assistant")
        self.ocr_button.setObjectName("SecondaryButton")
        self.ocr_button.setMinimumHeight(54)
        self.settings_button = QPushButton("Accessibility Settings")
        self.settings_button.setObjectName("SecondaryButton")
        self.settings_button.setMinimumHeight(54)
        row.addWidget(self.sign_button)
        row.addWidget(self.vision_button)
        row.addWidget(self.ocr_button)
        row.addWidget(self.settings_button)
        quick_layout.addLayout(row)
        layout.addWidget(quick)

        info = panel()
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(22, 20, 22, 20)
        info_layout.setSpacing(8)
        title = QLabel("HOW TO GET STARTED")
        title.setObjectName("BrandAccent")
        info_layout.addWidget(title)
        note = QLabel(
            "1. Open Sign Recognition and hold a supported Arabic letter in view.\n"
            "2. Add accepted letters to build a word or sentence.\n"
            "3. Read the text aloud, or use Vision Assistant to identify objects around you."
        )
        note.setObjectName("Muted")
        note.setWordWrap(True)
        info_layout.addWidget(note)
        layout.addWidget(info)
        layout.addStretch(1)

        self.sign_button.clicked.connect(self.open_sign.emit)
        self.vision_button.clicked.connect(self.open_vision.emit)
        self.ocr_button.clicked.connect(self.open_ocr.emit)
        self.settings_button.clicked.connect(self.open_settings.emit)

    def _status_card(self, eyebrow, value, detail):
        card = panel("MetricPanel")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(5)
        label = QLabel(eyebrow)
        label.setObjectName("BrandAccent")
        value_label = QLabel(value)
        value_label.setObjectName("SectionTitle")
        detail_label = QLabel(detail)
        detail_label.setObjectName("Muted")
        detail_label.setWordWrap(True)
        card_layout.addWidget(label)
        card_layout.addWidget(value_label)
        card_layout.addWidget(detail_label)
        card.value_label = value_label
        return card

    def update_status(self, sign_ready, vision_ready, speech_ready=None):
        self.sign_status.value_label.setText("Ready" if sign_ready else "Needs setup")
        self.vision_status.value_label.setText("Ready" if vision_ready else "Needs setup")
        self.speech_status.value_label.setText(
            "Starting…" if speech_ready is None else ("Available" if speech_ready else "Check voice")
        )

    def update_speech_status(self, message):
        value = str(message).casefold()
        if "unavailable" in value or "failed" in value or "cannot speak" in value:
            self.speech_status.value_label.setText("Check voice")
        elif "ready" in value or "finished" in value:
            self.speech_status.value_label.setText("Available")
