from PySide6.QtGui import QFont
import re

DARK = """
QWidget {
    background: #0c1118;
    color: #e8eef5;
    font-family: 'Segoe UI', Arial;
    font-size: 10pt;
}
QLabel { background: transparent; }
QMainWindow { background: #0c1118; }
QFrame#Sidebar {
    background: #111923;
    border-right: 1px solid #263340;
}
QLabel#Brand { color: #f4f8fb; font-size: 20pt; font-weight: 800; }
QLabel#BrandAccent { color: #48d6b2; font-size: 8pt; font-weight: 800; letter-spacing: 1.4px; }
QLabel#Muted, QLabel#MetricCaption { color: #91a0b1; }
QLabel#PageTitle { color: #f4f8fb; font-size: 23pt; font-weight: 800; }
QLabel#PageSubtitle { color: #93a2b3; font-size: 10pt; }
QLabel#SectionTitle { color: #f4f8fb; font-size: 11pt; font-weight: 800; }
QLabel#Metric { color: #f4f8fb; font-size: 25pt; font-weight: 800; }
QLabel#SignResult { color: #f4f8fb; background: #0b151d; border: 1px solid #2c4650; border-radius: 14px; font-size: 76pt; font-weight: 900; }
QLabel#StatusPill {
    background: #172a2a; color: #7ee6c9; border: 1px solid #285348;
    border-radius: 10px; padding: 7px 11px; font-weight: 700;
}
QLabel#StatusPill[warning="true"] {
    background: #302719; color: #f2c879; border: 1px solid #6b512a;
}
QFrame#Panel {
    background: #121c27; border: 1px solid #293847; border-radius: 16px;
}
QFrame#MetricPanel {
    background: #17232f; border: 1px solid #2b3b4b; border-radius: 13px;
}
QFrame#CameraPanel {
    background: #080e14; border: 1px solid #2c3c4b; border-radius: 16px;
}
QPushButton {
    background: #28b995; color: #071712; border: 0; border-radius: 10px;
    padding: 11px 15px; font-weight: 800; min-height: 20px;
}
QPushButton:hover { background: #42d2ae; }
QPushButton:pressed { background: #169879; }
QPushButton:disabled { background: #293746; color: #718092; }
QPushButton#SecondaryButton {
    background: #1b2a38; color: #dce7f0; border: 1px solid #35495c;
}
QPushButton#SecondaryButton:hover { background: #25394b; }
QPushButton#DangerButton {
    background: #38242a; color: #ffb8c0; border: 1px solid #6b3943;
}
QPushButton#NavButton {
    background: transparent; color: #9aabba; border: 0; border-radius: 9px;
    text-align: left; padding: 13px 14px; font-weight: 650;
}
QPushButton#NavButton:hover { background: #1b2935; color: #f4f8fb; }
QPushButton#NavButton[active="true"] {
    background: #183d39; color: #70e4c5; border: 1px solid #28685c;
}
QLineEdit, QComboBox, QTextEdit {
    background: #0c151e; color: #e8eef5; border: 1px solid #334657;
    border-radius: 9px; padding: 9px; selection-background-color: #168f78;
}
QComboBox::drop-down { border: 0; width: 25px; }
QCheckBox { color: #e8eef5; spacing: 9px; }
QCheckBox::indicator { width: 18px; height: 18px; }
QScrollBar:vertical { background: #111923; width: 9px; margin: 2px; }
QScrollBar::handle:vertical { background: #35495c; border-radius: 4px; min-height: 24px; }
QToolTip { background: #17232f; color: #f4f8fb; border: 1px solid #415568; padding: 5px; }
"""

LIGHT = """
QWidget {
    background: #f4f7fb; color: #243247;
    font-family: 'Segoe UI', Arial; font-size: 10pt;
}
QLabel { background: transparent; }
QMainWindow { background: #f4f7fb; }
QFrame#Sidebar { background: #ffffff; border-right: 1px solid #dce4ee; }
QLabel#Brand { color: #17263b; font-size: 20pt; font-weight: 800; }
QLabel#BrandAccent { color: #087f70; font-size: 8pt; font-weight: 800; letter-spacing: 1.4px; }
QLabel#Muted, QLabel#MetricCaption { color: #718096; }
QLabel#PageTitle { color: #17263b; font-size: 23pt; font-weight: 800; }
QLabel#PageSubtitle { color: #68788e; font-size: 10pt; }
QLabel#SectionTitle { color: #23364d; font-size: 11pt; font-weight: 800; }
QLabel#Metric { color: #17263b; font-size: 25pt; font-weight: 800; }
QLabel#SignResult { color: #17263b; background: #ffffff; border: 1px solid #dce4ee; border-radius: 14px; font-size: 76pt; font-weight: 900; }
QLabel#StatusPill { background: #e3f5ef; color: #087f70; border: 1px solid #b8e4d6; border-radius: 10px; padding: 7px 11px; font-weight: 700; }
QLabel#StatusPill[warning="true"] { background: #fff4df; color: #946200; border: 1px solid #f0d69b; }
QFrame#Panel { background: #ffffff; border: 1px solid #dce4ee; border-radius: 16px; }
QFrame#MetricPanel { background: #ffffff; border: 1px solid #dce4ee; border-radius: 13px; }
QFrame#CameraPanel { background: #eaf0f6; border: 1px solid #d0dbe7; border-radius: 16px; }
QPushButton { background: #0e9f83; color: #ffffff; border: 0; border-radius: 10px; padding: 11px 15px; font-weight: 800; min-height: 20px; }
QPushButton:hover { background: #087f70; }
QPushButton:pressed { background: #066b5e; }
QPushButton:disabled { background: #dce4ee; color: #8996a8; }
QPushButton#SecondaryButton { background: #edf3f8; color: #34465c; border: 1px solid #d3deea; }
QPushButton#SecondaryButton:hover { background: #e0eaf3; }
QPushButton#DangerButton { background: #fff0f0; color: #b42332; border: 1px solid #f0c8cd; }
QPushButton#NavButton { background: transparent; color: #607086; border: 0; border-radius: 9px; text-align: left; padding: 13px 14px; font-weight: 650; }
QPushButton#NavButton:hover { background: #edf3f8; color: #17263b; }
QPushButton#NavButton[active="true"] { background: #e0f4ef; color: #087f70; border: 1px solid #bce5d9; }
QLineEdit, QComboBox, QTextEdit { background: #ffffff; color: #243247; border: 1px solid #cbd7e4; border-radius: 9px; padding: 9px; selection-background-color: #9cddce; }
QComboBox::drop-down { border: 0; width: 25px; }
QCheckBox { color: #34465c; spacing: 9px; }
QCheckBox::indicator { width: 18px; height: 18px; }
QScrollBar:vertical { background: #edf2f7; width: 9px; margin: 2px; }
QScrollBar::handle:vertical { background: #c1cedc; border-radius: 4px; min-height: 24px; }
QToolTip { background: #ffffff; color: #243247; border: 1px solid #cbd7e4; padding: 5px; }
"""

def apply_theme(app, font_scale=1.0, theme="Dark"):
    """Apply the selected palette and scale every explicit QSS font-size declaration."""
    base = LIGHT if str(theme).lower() == "light" else DARK
    scale = max(0.80, min(1.60, float(font_scale)))

    def scale_font(match):
        value = float(match.group(2)) * scale
        return f"{match.group(1)}{value:g}{match.group(3)}"

    scaled = re.sub(
        r"(font-size\s*:\s*)([0-9]+(?:\.[0-9]+)?)(pt|px)",
        scale_font,
        base,
        flags=re.IGNORECASE,
    )
    app.setStyleSheet(scaled)
    app.setFont(QFont("Segoe UI", max(9, round(10 * scale))))
