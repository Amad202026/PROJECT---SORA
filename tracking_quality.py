from collections import Counter
import time


class TrackingQuality:
    def __init__(self, report_seconds=10.0):
        self.report_seconds = report_seconds
        self.started_at = None
        self.counts = Counter()
        self.valid_frames = 0
        self.total_frames = 0

    def update(self, detection_status, features):
        if self.started_at is None:
            self.started_at = time.perf_counter()
        self.total_frames += 1
        self.counts[detection_status] += 1

        if features is not None:
            self.valid_frames += 1

        elapsed = time.perf_counter() - self.started_at

        if elapsed < self.report_seconds:
            return

        valid_percent = (
            100.0 * self.valid_frames / self.total_frames
        )
        processed_fps = self.total_frames / elapsed

        print("\n--- Tracking quality report ---")
        print(f"Duration: {elapsed:.1f}s")
        print(f"Processed frames: {self.total_frames}")
        print(f"Processing rate: {processed_fps:.1f} FPS")
        print(f"Usable measurement frames: {valid_percent:.1f}%")

        for status, count in self.counts.items():
            percent = 100.0 * count / self.total_frames
            print(f"  {status}: {percent:.1f}%")

        print("-------------------------------\n")

        self.started_at = time.perf_counter()
        self.counts.clear()
        self.valid_frames = 0
        self.total_frames = 0