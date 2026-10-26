from collections import deque
import time


class PostureReminder:
    KNOWN_STATES = {"NEAR_REFERENCE", "LOWER_HEAD_POSITION"}

    def __init__(
        self,
        window_seconds=60.0,
        minimum_coverage=0.8,
        minimum_lower_fraction=0.8,
        recovery_seconds=5.0,
        maximum_gap=1.0,
    ):
        self.window_seconds = window_seconds
        self.minimum_coverage = minimum_coverage
        self.minimum_lower_fraction = minimum_lower_fraction
        self.recovery_seconds = recovery_seconds
        self.maximum_gap = maximum_gap

        self.reset()

    def reset(self):
        self.intervals = deque()
        self.started_at = None
        self.previous_time = None
        self.previous_state = None

        self.alert_active = False
        self.recovery_started_at = None

        self.coverage = 0.0
        self.lower_fraction = 0.0

    def update(self, state, now=None):
        now = time.perf_counter() if now is None else now

        if self.started_at is None:
            self.started_at = now

        gap = None

        if self.previous_time is not None:
            gap = now - self.previous_time

            # Count only short intervals with matching known endpoints.
            # Missing or uncertain intervals remain unobserved.
            if (
                0 < gap <= self.maximum_gap
                and state in self.KNOWN_STATES
                and state == self.previous_state
            ):
                self.intervals.append(
                    (self.previous_time, now, state)
                )

        self.previous_time = now
        self.previous_state = state

        cutoff = now - self.window_seconds

        while self.intervals and self.intervals[0][1] <= cutoff:
            self.intervals.popleft()

        known_seconds = 0.0
        lower_seconds = 0.0

        for start, end, interval_state in self.intervals:
            duration = max(0.0, end - max(start, cutoff))
            known_seconds += duration

            if interval_state == "LOWER_HEAD_POSITION":
                lower_seconds += duration

        self.coverage = known_seconds / self.window_seconds

        self.lower_fraction = (
            lower_seconds / known_seconds
            if known_seconds > 0
            else 0.0
        )

        if self.alert_active:
            if state != "NEAR_REFERENCE":
                self.recovery_started_at = None

            elif (
                self.recovery_started_at is None
                or gap is None
                or gap > self.maximum_gap
            ):
                self.recovery_started_at = now

            elif now - self.recovery_started_at >= self.recovery_seconds:
                self.reset()
                return "RESOLVED"

            return None

        window_ready = (
            now - self.started_at >= self.window_seconds
        )

        if (
            window_ready
            and state == "LOWER_HEAD_POSITION"
            and self.coverage >= self.minimum_coverage
            and self.lower_fraction >= self.minimum_lower_fraction
        ):
            self.alert_active = True
            self.recovery_started_at = None
            return "REMIND"

        return None
