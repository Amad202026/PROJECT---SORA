import time


class PostureState:
    def __init__(self):
        # Experimental thresholds for initial testing.
        self.enter_drop = 0.07
        self.exit_drop = 0.04
        self.confirm_seconds = 2.0

        self.reset()

    def reset(self):
        self.state = "UNKNOWN"
        self.candidate = None
        self.candidate_since = None

    def update(self, features, baseline, now=None):
        if features is None or baseline is None:
            self.reset()
            return self.state

        # A positive drop means the ratio fell below the reference.
        drop = (
            baseline["head_height_ratio"]
            - features["head_height_ratio"]
        )

        if drop >= self.enter_drop:
            desired = "LOWER_HEAD_POSITION"

        elif drop <= self.exit_drop:
            desired = "NEAR_REFERENCE"

        else:
            # Between thresholds, keep the confirmed state.
            # Cancel any pending transition.
            self.candidate = None
            self.candidate_since = None
            return self.state

        if desired == self.state:
            self.candidate = None
            self.candidate_since = None
            return self.state

        now = time.perf_counter() if now is None else now

        if desired != self.candidate:
            self.candidate = desired
            self.candidate_since = now

        elif now - self.candidate_since >= self.confirm_seconds:
            self.state = desired
            self.candidate = None
            self.candidate_since = None

        return self.state
