"""Independent facial landmarks for drinking; no identity recognition."""
from pathlib import Path
import cv2
import numpy as np


class FaceAnchor:
    def __init__(self):
        model = Path(__file__).parent / 'models/face_detection_yunet_2023mar.onnx'
        self.detector = cv2.FaceDetectorYN.create(str(model), '', (640, 480), 0.7, 0.3, 5000)
        self.multiple = False

    def observe(self, frame):
        height, width = frame.shape[:2]
        self.detector.setInputSize((width, height))
        _, faces = self.detector.detect(frame)
        self.multiple = faces is not None and len(faces) > 1
        if faces is None or len(faces) != 1:
            return None
        face = faces[0]
        if not np.isfinite(face).all():
            return None
        x, y, w, h = face[:4]
        mouth = (face[10:12] + face[12:14]) / 2
        if (w < 35 or h < 45 or not (0 <= mouth[0] < width and 0 <= mouth[1] < height)
                or not (x <= mouth[0] <= x+w and y+0.35*h <= mouth[1] <= y+h)):
            return None
        return mouth.astype(float), float(2*w)
