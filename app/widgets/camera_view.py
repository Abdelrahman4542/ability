import cv2

from PySide6.QtCore import QTimer, Signal, Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel


HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20), (0, 17)
]


class CameraView(QFrame):
    camera_state_changed = Signal(bool)
    frame_updated = Signal(object)

    def __init__(self):
        super().__init__()
        self.setObjectName("CameraPanel")
        self.capture = None
        self.device_index = 0
        self.current_frame = None
        self.detection_bbox = None
        self.detection_label = None
        self.hand_landmarks = None
        self.hand_overlays = []
        self.object_overlays = []
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        self.preview = QLabel("CAMERA PREVIEW\n\nStart the camera or upload an image.")
        self.preview.setObjectName("CameraPreview")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(300, 220)
        self.preview.setWordWrap(True)
        layout.addWidget(self.preview)

    def set_camera_index(self, index):
        self.device_index = max(0, int(index))
        if self.capture is not None:
            self.stop_camera()

    def start_camera(self):
        if self.capture is not None:
            return True

        # Try Windows DirectShow first, then Media Foundation and OpenCV default.
        candidates = [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]
        for backend in candidates:
            cap = cv2.VideoCapture(self.device_index, backend)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                ok, test_frame = cap.read()
                if ok and test_frame is not None:
                    self.capture = cap
                    self.current_frame = test_frame
                    self.timer.start(33)
                    self.camera_state_changed.emit(True)
                    return True
            cap.release()

        self.preview.setText(
            "Camera unavailable.\n\nClose apps using the webcam, check Windows "
            "camera privacy permissions, then try again."
        )
        self.camera_state_changed.emit(False)
        return False

    def stop_camera(self):
        self.timer.stop()
        if self.capture is not None:
            self.capture.release()
            self.capture = None
        self.detection_bbox = None
        self.detection_label = None
        self.hand_landmarks = None
        self.hand_overlays = []
        self.object_overlays = []
        if self.current_frame is not None:
            self.show_frame(self.current_frame)
        else:
            self.preview.setText("CAMERA STOPPED")
        self.camera_state_changed.emit(False)

    def update_frame(self):
        if self.capture is None:
            return
        ok, frame = self.capture.read()
        if not ok or frame is None:
            return
        self.current_frame = frame
        self.show_frame(frame)
        # Emit after painting the raw frame; the recognition page can now
        # paint landmarks/prediction on top without being overwritten.
        self.frame_updated.emit(frame.copy())

    def load_image(self, path):
        frame = cv2.imread(str(path))
        if frame is None:
            self.preview.setText("Could not open this image.\nTry a JPG or PNG file.")
            return False
        self.current_frame = frame
        self.detection_bbox = None
        self.detection_label = None
        self.hand_landmarks = None
        self.hand_overlays = []
        self.object_overlays = []
        self.show_frame(frame)
        return True

    def set_detection_overlay(self, bbox=None, label=None, landmarks=None):
        self.detection_bbox = bbox
        self.detection_label = label
        self.hand_landmarks = landmarks
        self.hand_overlays = []
        self.object_overlays = []
        if self.current_frame is not None:
            self.show_frame(self.current_frame)

    def set_hand_overlays(self, hands):
        self.hand_overlays = list(hands or [])
        self.object_overlays = []
        self.detection_bbox = None
        self.detection_label = None
        self.hand_landmarks = None
        if self.current_frame is not None:
            self.show_frame(self.current_frame)

    def set_object_overlays(self, detections):
        """Persist object boxes so they remain visible on each subsequent camera frame."""
        self.object_overlays = list(detections or [])
        self.hand_overlays = []
        self.hand_landmarks = None
        self.detection_bbox = None
        self.detection_label = None
        if self.current_frame is not None:
            self.show_frame(self.current_frame)

    def _draw_hand_landmarks(self, image, landmarks):
        if not landmarks:
            return
        height, width = image.shape[:2]
        points = []
        for landmark in landmarks:
            x = int(max(0, min(width - 1, landmark[0] * width)))
            y = int(max(0, min(height - 1, landmark[1] * height)))
            points.append((x, y))
        for start, end in HAND_CONNECTIONS:
            cv2.line(image, points[start], points[end], (66, 214, 181), 2, cv2.LINE_AA)
        for point in points:
            cv2.circle(image, point, 4, (239, 249, 247), -1, cv2.LINE_AA)
            cv2.circle(image, point, 2, (30, 166, 140), -1, cv2.LINE_AA)

    def show_frame(self, frame):
        display = frame.copy()
        self._draw_hand_landmarks(display, self.hand_landmarks)
        for hand in self.hand_overlays:
            self._draw_hand_landmarks(display, hand.get("landmarks"))
            bbox = hand.get("bbox")
            if bbox:
                x1, y1, x2, y2 = bbox
                cv2.rectangle(display, (x1, y1), (x2, y2), (66, 214, 181), 2)
                tag = f'Hand {hand.get("hand_number", "")}: {hand.get("label", "Detected")}'
                cv2.putText(display, tag, (x1, max(26, y1 - 10)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, (66, 214, 181), 2, cv2.LINE_AA)
        for item in self.object_overlays:
            box = item.get("box")
            if not box or len(box) != 4:
                continue
            x1, y1, x2, y2 = map(int, box)
            label = f'{item.get("label", "Object")} {float(item.get("confidence", 0)):.0%}'
            cv2.rectangle(display, (x1, y1), (x2, y2), (66, 214, 181), 2)
            cv2.putText(display, label, (x1, max(26, y1 - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (20, 45, 40), 3, cv2.LINE_AA)
            cv2.putText(display, label, (x1, max(26, y1 - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (120, 245, 210), 1, cv2.LINE_AA)
        if self.detection_bbox is not None:
            x1, y1, x2, y2 = self.detection_bbox
            cv2.rectangle(display, (x1, y1), (x2, y2), (66, 214, 181), 2)
            if self.detection_label:
                cv2.putText(display, str(self.detection_label), (x1, max(26, y1 - 10)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.85, (66, 214, 181), 2, cv2.LINE_AA)

        rgb = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimage = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888).copy()
        pixmap = QPixmap.fromImage(qimage).scaled(
            self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.preview.setPixmap(pixmap)

    def show_annotated_frame(self, frame):
        """Display an annotated copy without replacing the original input frame."""
        if frame is not None:
            self.show_frame(frame)

    def resizeEvent(self, event):
        if self.current_frame is not None:
            self.show_frame(self.current_frame)
        super().resizeEvent(event)

    def closeEvent(self, event):
        self.stop_camera()
        super().closeEvent(event)
