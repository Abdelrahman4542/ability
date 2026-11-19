from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QMainWindow,
    QPushButton, QStackedWidget, QVBoxLayout, QWidget, QScrollArea
)

from app.pages.sign_page import SignPage
from app.pages.vision_page import VisionPage
from app.pages.settings_page import SettingsPage
from app.pages.dashboard_page import DashboardPage
from app.pages.about_page import AboutPage
from app.pages.ocr_page import OCRPage
from app.theme import apply_theme


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AbilityBridge AI | Accessibility Workspace")
        self.setMinimumSize(760, 580)
        self.resize(1240, 800)
        screen = QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            self.resize(min(1240, available.width()), min(800, available.height()))
            self.move(available.center() - self.rect().center())

        shell = QWidget()
        shell_layout = QHBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(220)
        side = QVBoxLayout(self.sidebar)
        side.setContentsMargins(18, 26, 18, 18)
        side.setSpacing(9)

        brand = QLabel("AbilityBridge")
        brand.setObjectName("Brand")
        self.brand_label = brand
        side.addWidget(brand)
        tagline = QLabel("ACCESSIBILITY WORKSPACE")
        tagline.setObjectName("BrandAccent")
        self.tagline_label = tagline
        side.addWidget(tagline)
        side.addSpacing(34)

        section = QLabel("WORKSPACE")
        section.setObjectName("Muted")
        self.workspace_label = section
        side.addWidget(section)

        self.stack = QStackedWidget()
        self.dashboard_page = DashboardPage()
        self.sign_page = SignPage()
        self.vision_page = VisionPage()
        self.ocr_page = OCRPage()
        self.settings_page = SettingsPage()
        self.about_page = AboutPage()
        for page in (self.dashboard_page, self.sign_page, self.vision_page, self.ocr_page, self.settings_page, self.about_page):
            self.stack.addWidget(page)

        self.nav_buttons = []
        self.nav_items = [
            ("⌂    Dashboard", "⌂", 0),
            ("◉    Sign recognition", "◉", 1),
            ("◈    Vision assistant", "◈", 2),
            ("▤    OCR assistant", "▤", 3),
            ("⚙    Preferences", "⚙", 4),
            ("ⓘ    About", "ⓘ", 5),
        ]
        for title, compact_title, index in self.nav_items:
            button = QPushButton(title)
            button.setObjectName("NavButton")
            button.setMinimumHeight(48)
            button.clicked.connect(lambda checked=False, i=index: self.navigate(i))
            side.addWidget(button)
            self.nav_buttons.append(button)

        side.addStretch()
        version = QLabel("ABILITYBRIDGE AI  •  4.0")
        version.setObjectName("BrandAccent")
        self.version_label = version
        side.addWidget(version)
        note = QLabel("Arabic static signs · one-hand tracking")
        note.setObjectName("Muted")
        note.setWordWrap(True)
        self.note_label = note
        side.addWidget(note)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        self.content_layout = content_layout
        content_layout.setContentsMargins(26, 20, 26, 20)
        page_scroll = QScrollArea()
        page_scroll.setWidgetResizable(True)
        page_scroll.setFrameShape(QFrame.NoFrame)
        page_scroll.setWidget(self.stack)
        content_layout.addWidget(page_scroll)

        shell_layout.addWidget(self.sidebar)
        shell_layout.addWidget(content, 1)
        self.setCentralWidget(shell)

        self.navigate(0)
        apply_theme(
            QApplication.instance(),
            float(self.settings_page.font_size.currentData()),
            self.settings_page.theme.currentText(),
        )
        self.dashboard_page.open_sign.connect(lambda: self.navigate(1))
        self.dashboard_page.open_vision.connect(lambda: self.navigate(2))
        self.dashboard_page.open_ocr.connect(lambda: self.navigate(3))
        self.dashboard_page.open_settings.connect(lambda: self.navigate(4))
        self.dashboard_page.update_status(
            self.sign_page.service is not None and self.sign_page.service.model is not None,
            self.vision_page.service.model is not None,
            self.vision_page.tts.available,
        )
        self.settings_page.settings_changed.connect(self.on_settings_changed)
        self.settings_page.camera_changed.connect(self.on_camera_changed)
        self.settings_page.confidence_changed.connect(self.sign_page.set_confidence_threshold)
        self.on_camera_changed(int(self.settings_page.camera_index.currentData()))
        self.sign_page.set_confidence_threshold(float(self.settings_page.confidence_threshold.currentData()))
        self.sign_page.speak_requested.connect(self.vision_page.tts.speak)
        self.sign_page.stop_speech_requested.connect(self.vision_page.tts.stop)
        self.ocr_page.speak_requested.connect(self.vision_page.tts.speak)
        self.ocr_page.stop_speech_requested.connect(self.vision_page.tts.stop)
        self.vision_page.tts.status_changed.connect(self.sign_page.on_speech_status)
        self.vision_page.tts.status_changed.connect(self.ocr_page.status.setText)
        self.vision_page.tts.status_changed.connect(self.dashboard_page.update_speech_status)

    def resizeEvent(self, event):
        compact = self.width() < 1020
        if hasattr(self, "sidebar"):
            self.sidebar.setFixedWidth(76 if compact else 220)
        for label_name in ("brand_label", "tagline_label", "workspace_label", "version_label", "note_label"):
            label = getattr(self, label_name, None)
            if label is not None:
                label.setVisible(not compact)
        for index, button in enumerate(getattr(self, "nav_buttons", [])):
            full_title, compact_title, _ = self.nav_items[index]
            button.setText(compact_title if compact else full_title)
            button.setToolTip(full_title)
            button.setMinimumHeight(46 if compact else 48)
        margin = 14 if compact else 26
        if hasattr(self, "content_layout"):
            self.content_layout.setContentsMargins(margin, 16, margin, 16)
        super().resizeEvent(event)

    def navigate(self, index):
        previous = self.stack.currentIndex()
        # A single physical webcam can only be owned by one page at a time.
        # Release it before switching to the other camera workflow.
        if previous != index:
            if previous == 1:
                self.sign_page.camera.stop_camera()
            elif previous == 2:
                self.vision_page.camera.stop_camera()
            elif previous == 3:
                self.ocr_page.camera.stop_camera()
            # Stop an utterance when leaving either workflow so speech does not
            # continue unexpectedly after navigation.
            self.vision_page.tts.stop()
        self.stack.setCurrentIndex(index)
        for i, button in enumerate(self.nav_buttons):
            button.setProperty("active", i == index)
            button.style().unpolish(button)
            button.style().polish(button)

    def on_settings_changed(self, font_scale, theme):
        apply_theme(QApplication.instance(), font_scale, theme)

    def on_camera_changed(self, camera_index):
        self.sign_page.camera.set_camera_index(camera_index)
        self.vision_page.camera.set_camera_index(camera_index)
        self.ocr_page.camera.set_camera_index(camera_index)

    def closeEvent(self, event):
        try:
            self.sign_page.shutdown()
        except Exception:
            pass
        try:
            self.vision_page.shutdown()
        except Exception:
            pass
        try:
            self.ocr_page.shutdown()
        except Exception:
            pass
        super().closeEvent(event)
