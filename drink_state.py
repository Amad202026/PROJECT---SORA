"""Session water-reminder clock and undo."""


class HydrationClock:
    def __init__(self, interval=3600.0):
        self.interval = interval
        self.elapsed = 0.0
        self.last_at = None
        self.was_paused = False
        self.due = False
        self.count = 0
        self.undo_snapshot = None

    def update(self, now, present, paused=False):
        if self.last_at is not None and not paused and not self.was_paused:
            self.elapsed += max(0, now - self.last_at)
        self.last_at, self.was_paused = now, paused
        self.due = not paused and present and self.elapsed >= self.interval

    def record(self, now, source):
        self.undo_snapshot = (now, self.elapsed, self.count, source)
        self.elapsed, self.due = 0.0, False
        self.last_at = now
        self.count += 1

    def undo(self, now):
        if self.undo_snapshot is None:
            return False
        stamp, elapsed, count, source = self.undo_snapshot
        if now - stamp > 30 or source != 'automatic_gesture':
            return False
        # elapsed contains only unpaused time since the mistaken record.
        self.elapsed += elapsed
        self.count = count
        self.undo_snapshot = None
        return True
