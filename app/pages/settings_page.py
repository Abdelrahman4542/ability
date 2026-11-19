from PySide6.QtCore import Signal, QSettings
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox
)
from app.pages.common import page_header, panel


class SettingsPage(QWidget):
    settings_changed = Signal(float, str)
    camera_changed = Signal(int)
    confidence_changed = Signal(float)

    def __init__(self):
        super().__init__()
        self.settings = QSettings("AbilityBridge", "AbilityBridgeAI")

        # Remove the old high-contrast preference so it cannot override themes.
        self.settings.remove("high_contrast")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        layout.addWidget(page_header(
            "Settings & Accessibility",
            "Choose Light or Dark appearance and adjust interface text size. "
            "Changes apply immediately and are saved automatically.",
            "PREFERENCES"
        ))

        appearance = panel()
        form = QVBoxLayout(appearance)
        form.setContentsMargins(24, 22, 24, 22)
        form.setSpacing(14)
        form.addWidget(QLabel("APPEARANCE", objectName="BrandAccent"))

        theme_row = QHBoxLayout()
        theme_label = QLabel("Color theme")
        self.theme = QComboBox()
        self.theme.addItems(["Light", "Dark"])
        self.theme.setMaximumWidth(260)
        saved_theme = str(self.settings.value("theme", "Dark"))
        self.theme.setCurrentText(saved_theme if saved_theme in ("Light", "Dark") else "Dark")
        theme_row.addWidget(theme_label)
        theme_row.addStretch()
        theme_row.addWidget(self.theme)
        form.addLayout(theme_row)

        accessibility = panel()
        aform = QVBoxLayout(accessibility)
        aform.setContentsMargins(24, 22, 24, 22)
        aform.setSpacing(14)
        aform.addWidget(QLabel("READABILITY", objectName="BrandAccent"))

        font_row = QHBoxLayout()
        font_label = QLabel("Interface text size")
        self.font_size = QComboBox()
        self.font_size.addItem("Small", 0.90)
        self.font_size.addItem("Normal", 1.00)
        self.font_size.addItem("Large", 1.20)
        self.font_size.addItem("Extra large", 1.40)
        self.font_size.setMaximumWidth(260)
        saved_scale = float(self.settings.value("font_scale", 1.0))
        selected = min(
            range(self.font_size.count()),
            key=lambda i: abs(float(self.font_size.itemData(i)) - saved_scale)
        )
        self.font_size.setCurrentIndex(selected)
        font_row.addWidget(font_label)
        font_row.addStretch()
        font_row.addWidget(self.font_size)
        aform.addLayout(font_row)

        note = QLabel(
            "Text size changes headings, labels, buttons and input controls. "
            "It does not change camera resolution or the size of detected objects."
        )
        note.setObjectName("Muted")
        note.setWordWrap(True)
        aform.addWidget(note)

        camera = panel()
        camera_form = QVBoxLayout(camera)
        camera_form.setContentsMargins(24, 22, 24, 22)
        camera_form.setSpacing(14)
        camera_form.addWidget(QLabel("CAMERA", objectName="BrandAccent"))
        camera_row = QHBoxLayout()
        camera_label = QLabel("Webcam device")
        self.camera_index = QComboBox()
        for index in range(4):
            self.camera_index.addItem(f"Camera {index + 1}", index)
        self.camera_index.setMaximumWidth(260)
        saved_camera = int(self.settings.value("camera_index", 0))
        self.camera_index.setCurrentIndex(max(0, min(3, saved_camera)))
        camera_row.addWidget(camera_label)
        camera_row.addStretch()
        camera_row.addWidget(self.camera_index)
        camera_form.addLayout(camera_row)
        camera_note = QLabel("Choose the camera index used by both Sign Recognition and Vision Assistant. Restart the camera after changing it.")
        camera_note.setObjectName("Muted")
        camera_note.setWordWrap(True)
        camera_form.addWidget(camera_note)

        recognition = panel()
        recognition_form = QVBoxLayout(recognition)
        recognition_form.setContentsMargins(24, 22, 24, 22)
        recognition_form.setSpacing(14)
        recognition_form.addWidget(QLabel("SIGN RECOGNITION", objectName="BrandAccent"))
        threshold_row = QHBoxLayout()
        threshold_label = QLabel("Minimum live confidence")
        self.confidence_threshold = QComboBox()
        for threshold in (0.30, 0.35, 0.40, 0.45, 0.50, 0.55):
            self.confidence_threshold.addItem(f"{threshold:.0%}", threshold)
        self.confidence_threshold.setMaximumWidth(260)
        saved_threshold = float(self.settings.value("sign_confidence", 0.40))
        threshold_index = min(range(self.confidence_threshold.count()), key=lambda i: abs(float(self.confidence_threshold.itemData(i)) - saved_threshold))
        self.confidence_threshold.setCurrentIndex(threshold_index)
        threshold_row.addWidget(threshold_label)
        threshold_row.addStretch()
        threshold_row.addWidget(self.confidence_threshold)
        recognition_form.addLayout(threshold_row)
        threshold_note = QLabel("Lower values accept more uncertain poses; higher values reduce false letters but may reject more attempts. Temporal stability is still required.")
        threshold_note.setObjectName("Muted")
        threshold_note.setWordWrap(True)
        recognition_form.addWidget(threshold_note)

        speech = panel()
        speech_form = QVBoxLayout(speech)
        speech_form.setContentsMargins(24, 22, 24, 22)
        speech_form.setSpacing(14)
        speech_form.addWidget(QLabel("SPEECH", objectName="BrandAccent"))
        speech_row = QHBoxLayout()
        speech_label = QLabel("Speech voice")
        self.speech_voice = QComboBox()
        self.speech_voice.addItem("Prefer Arabic voice", "arabic")
        self.speech_voice.addItem("Windows default voice", "default")
        self.speech_voice.setMaximumWidth(260)
        saved_voice = str(self.settings.value("tts_voice", "arabic"))
        voice_index = self.speech_voice.findData(saved_voice)
        self.speech_voice.setCurrentIndex(max(0, voice_index))
        speech_row.addWidget(speech_label)
        speech_row.addStretch()
        speech_row.addWidget(self.speech_voice)
        speech_form.addLayout(speech_row)
        speech_note = QLabel(
            "Arabic speech requires an Arabic voice installed in Windows. "
            "If none is installed, Windows may fall back to its default voice."
        )
        speech_note.setObjectName("Muted")
        speech_note.setWordWrap(True)
        speech_form.addWidget(speech_note)

        layout.addWidget(appearance)
        layout.addWidget(accessibility)
        layout.addWidget(camera)
        layout.addWidget(recognition)
        layout.addWidget(speech)
        layout.addStretch()

        self.theme.currentIndexChanged.connect(self.apply_settings)
        self.font_size.currentIndexChanged.connect(self.apply_settings)
        self.speech_voice.currentIndexChanged.connect(self.save_speech_preference)
        self.camera_index.currentIndexChanged.connect(self.save_camera_preference)
        self.confidence_threshold.currentIndexChanged.connect(self.save_confidence_preference)

    def save_camera_preference(self, *_):
        value = int(self.camera_index.currentData())
        self.settings.setValue("camera_index", value)
        self.settings.sync()
        self.camera_changed.emit(value)

    def save_confidence_preference(self, *_):
        value = float(self.confidence_threshold.currentData())
        self.settings.setValue("sign_confidence", value)
        self.settings.sync()
        self.confidence_changed.emit(value)

    def save_speech_preference(self, *_):
        self.settings.setValue("tts_voice", str(self.speech_voice.currentData()))
        self.settings.sync()

    def apply_settings(self, *_):
        scale = float(self.font_size.currentData())
        theme = self.theme.currentText()
        self.settings.setValue("font_scale", scale)
        self.settings.setValue("theme", theme)
        self.settings.sync()
        self.settings_changed.emit(scale, theme)
