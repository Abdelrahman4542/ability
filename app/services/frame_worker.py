"""Small Qt worker wrapper for non-blocking camera inference tasks."""
from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class _TaskSignals(QObject):
    finished = Signal(object, int)
    failed = Signal(str, int)


class FrameTask(QRunnable):
    def __init__(self, callback, frame, generation=0):
        super().__init__()
        self.callback = callback
        self.frame = frame
        self.generation = int(generation)
        self.signals = _TaskSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self):
        try:
            self.signals.finished.emit(self.callback(self.frame), self.generation)
        except Exception as exc:
            self.signals.failed.emit(f"{type(exc).__name__}: {exc}", self.generation)
