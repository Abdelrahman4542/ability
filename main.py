import sys
from PySide6.QtWidgets import QApplication
from app.main_window import MainWindow
from app.theme import apply_theme

app = QApplication(sys.argv)
app.setApplicationName("AbilityBridge AI")
apply_theme(app)
window = MainWindow()
window.show()
sys.exit(app.exec())
