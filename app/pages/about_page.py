from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from app.pages.common import page_header, panel


class AboutPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        layout.addWidget(page_header(
            "About AbilityBridge AI",
            "An AI-powered desktop accessibility project focused on Arabic static sign recognition and visual assistance.",
            "PROJECT INFORMATION"
        ))
        sections = [
            ("ARABIC SIGN RECOGNITION", "CNN image classification for 32 ArASL sign classes, with one-hand MediaPipe localization and temporal smoothing."),
            ("VISION ASSISTANT", "YOLO11n live object detection with Arabic object labels and automatic spoken scene updates."),
            ("OCR ASSISTANT", "EasyOCR extracts printed Arabic and English text from uploaded images or camera captures, with optional read-aloud."),
            ("ACCESSIBILITY", "Arabic text-to-speech, right-to-left text formation, adjustable text size, theme, camera selection, and speech controls."),
            ("MODEL SCOPE", "The sign model recognizes static alphabet poses. It does not translate dynamic signs or full sign-language grammar."),
        ]
        for title_text, body_text in sections:
            card = panel()
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(22, 18, 22, 18)
            card_layout.setSpacing(7)
            title = QLabel(title_text)
            title.setObjectName("BrandAccent")
            body = QLabel(body_text)
            body.setObjectName("Muted")
            body.setWordWrap(True)
            card_layout.addWidget(title)
            card_layout.addWidget(body)
            layout.addWidget(card)
        layout.addStretch(1)
