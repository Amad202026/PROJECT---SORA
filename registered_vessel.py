"""User-selected vessel tracking. A tracked object is not proof of drinking."""
from pathlib import Path
import cv2
import numpy as np


class RegisteredVessel:
    minimum_score = 0.4
    grace_seconds = 1.5

    def __init__(self, model_path=None, factory=None, max_gap=1.0):
        self.model_path = model_path or Path(__file__).parent / 'models/object_tracking_vittrack_2023sep.onnx'
        self.factory = factory
        self.max_gap = max_gap
        self.clear()

    def clear(self):
        self.tracker = self.box = None
        self.last_at = self.uncertain_since = self.score = None
        self.message = 'R: register your vessel   X: clear registration'

    def register(self, frame, roi, now):
        self.clear()
        x, y, w, h = map(int, roi)
        height, width = frame.shape[:2]
        if min(w, h) < 24 or min(x, y) < 0 or x + w > width or y + h > height:
            self.message = 'Select the whole vessel inside the image (at least 24 pixels)'
            return False
        if np.std(cv2.cvtColor(frame[y:y+h, x:x+w], cv2.COLOR_BGR2GRAY)) < 2:
            self.message = 'Select a visible vessel including its edges'
            return False
        params = cv2.TrackerVit_Params()
        params.net = str(self.model_path)
        params.tracking_score_threshold = self.minimum_score
        tracker = self.factory(params) if self.factory else cv2.TrackerVit_create(params)
        tracker.init(frame, (x, y, w, h))
        self.tracker = tracker
        self.box = np.array([x, y, x+w, y+h], dtype=float)
        self.last_at = now
        self.message = 'Vessel registered - show it away from your mouth first'
        return True

    def lost(self):
        self.clear()
        self.message = 'Registered vessel lost - press R to select it again'
        return None

    def update(self, frame, now):
        if self.tracker is None:
            return None
        if now - self.last_at > self.max_gap:
            return self.lost()
        self.last_at = now
        located, roi = self.tracker.update(frame)
        self.score = float(self.tracker.getTrackingScore())
        x, y, w, h = roi
        height, width = frame.shape[:2]
        valid = (located and np.isfinite([x, y, w, h, self.score]).all()
                 and self.score >= self.minimum_score and min(w, h) >= 12
                 and x >= 0 and y >= 0 and x+w <= width and y+h <= height)
        if not valid:
            self.box = None
            if self.uncertain_since is None:
                self.uncertain_since = now
            if now - self.uncertain_since >= self.grace_seconds:
                return self.lost()
            self.message = 'Vessel tracking uncertain - no sip evidence counted'
            return None
        self.uncertain_since = None
        self.box = np.array([x, y, x+w, y+h], dtype=float)
        self.message = f'ViT vessel tracking: {self.score:.2f} (tracking score, not probability)'
        return {'box': self.box.copy(), 'label': 'registered vessel',
                'score': self.score, 'source': 'registered'}
