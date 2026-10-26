import json
import time
from pathlib import Path

import numpy as np


class PostureCalibration:
    def __init__(self, output_path):
        self.output_path = Path(output_path)
        self.duration = 3.0
        self.minimum_samples = 20
        self.maximum_duration = 15.0
        self.maximum_tracking_gap = 0.75

        self.active = False
        self.started_at = None
        self.samples = []
        self.baseline = None
        self.stable_since = None
        self.last_valid_at = None
        self.message = "Press C to calibrate"

    @staticmethod
    def extract_features(points, width, height):
        required = (0, 11, 12)

        if not all(index in points for index in required):
            return None

        nose = np.asarray(points[0], dtype=float)
        left = np.asarray(points[11], dtype=float)
        right = np.asarray(points[12], dtype=float)

        shoulder_center = (left + right) / 2.0
        shoulder_width = np.linalg.norm(left - right)

        # Reject nearly overlapping shoulder points.
        if shoulder_width < 0.05 * width:
            return None

        features = {
            "head_height_ratio": (
                shoulder_center[1] - nose[1]
            ) / shoulder_width,

            "head_offset_ratio": (
                nose[0] - shoulder_center[0]
            ) / shoulder_width,

            "shoulder_tilt_ratio": (
                left[1] - right[1]
            ) / shoulder_width,

            "shoulder_width_fraction": shoulder_width / width,

            "shoulder_center_x": shoulder_center[0] / width,
            "shoulder_center_y": shoulder_center[1] / height,

            "frame_width": float(width),
            "frame_height": float(height),
        }

        if not np.isfinite(list(features.values())).all():
            return None

        return features

    def start(self):
        self.active = True
        self.started_at = time.perf_counter()
        self.samples = []
        self.stable_since = None
        self.last_valid_at = None
        self.message = "Calibrating - hold your reference position"
        print(self.message)

    def update(self, points, width, height):
        features = self.extract_features(points, width, height)

        if not self.active:
            return features

        now = time.perf_counter()
        elapsed = now - self.started_at
        if elapsed >= self.maximum_duration:
            self.active = False
            self.samples = []
            self.message = "Calibration timed out - show head and shoulders, press C to retry"
            return features

        if features is None:
            if self.last_valid_at is None or now - self.last_valid_at > self.maximum_tracking_gap:
                self.samples = []
                self.stable_since = None
            self.message = "Calibrating - show your nose and both shoulders"
            return None

        if self.last_valid_at is not None and now - self.last_valid_at > self.maximum_tracking_gap:
            self.samples = []
            self.stable_since = None
        self.last_valid_at = now
        if self.stable_since is None:
            self.stable_since = now
        self.samples.append(features)
        # A moving target should not become the saved reference.
        recent = self.samples[-15:]
        if len(recent) >= 5:
            limits = {"head_height_ratio": 0.10, "shoulder_width_fraction": 0.06,
                      "shoulder_center_x": 0.035, "shoulder_center_y": 0.035}
            moving = any(
                np.percentile([sample[name] for sample in recent], 90)
                - np.percentile([sample[name] for sample in recent], 10) > limit
                for name, limit in limits.items()
            )
            if moving:
                self.samples = [features]
                self.stable_since = now
                self.message = "Movement detected - hold your reference position steady"
                return features

        stable_elapsed = now - self.stable_since
        if stable_elapsed < self.duration or len(self.samples) < self.minimum_samples:
            remaining = max(0, self.duration - stable_elapsed)
            self.message = f"Calibrating - hold still: {remaining:.1f}s"
            return features

        self.active = False

        baseline = {
            name: float(np.median([
                sample[name] for sample in self.samples
            ]))
            for name in self.samples[0]
        }

        payload = {
            "schema_version": 1,
            "sample_count": len(self.samples),
            "duration_seconds": elapsed,
            "stable_seconds": stable_elapsed,
            "features": baseline,
        }

        try:
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.output_path.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(payload, indent=2),
                encoding="utf-8",
            )
            temporary.replace(self.output_path)
        except OSError as error:
            self.message = "Calibration could not be saved"
            print(f"{self.message}: {error}")
            return features

        self.baseline = baseline
        self.message = "Reference saved - press C to recalibrate"
        print(f"Calibration saved: {self.output_path.name}")
        print(f"Samples collected: {len(self.samples)}")

        return features
