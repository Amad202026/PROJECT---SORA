"""Quiet gesture estimates: approach, sustained contact, observed retreat.

No question popup and no automatic credit for missing tracking or weak straw cues.
Thresholds are prototype heuristics, not validated ingestion measurements.
"""


class DrinkCycle:
    def __init__(self):
        self.cooldown_until = 0.0
        self.reset()

    def reset(self):
        # A tracking reset must never erase a global cooldown.
        self.track_id = None
        self.last_at = self.last_valid = None
        self.phase = 'WAIT'
        self.away_time = self.contact_time = self.fresh_time = self.retreat_time = 0.0
        self.peak_distance = 0.0
        self.started = None
        self.label = 'Show the vessel away from your mouth first'

    def cooldown(self, now):
        self.reset()
        self.cooldown_until = now + 10.0

    def update(self, evidence, now):
        previous = self.last_at
        dt = 0.0 if previous is None else max(0.0, now - previous)
        if previous is not None and dt > 0.8:
            self.reset()
            dt = 0.0
        self.last_at = now
        if now < self.cooldown_until:
            self.label = 'Sip recorded / cooldown'
            return None
        usable = evidence.valid and evidence.track_id >= 0
        if not usable:
            if self.last_valid is None or now - self.last_valid > 0.6:
                self.reset()
                self.last_at = now
            self.label = evidence.reason
            return None
        if evidence.track_id != self.track_id:
            self.reset()
            self.last_at = now
            self.track_id = evidence.track_id
            dt = 0.0
        elif self.last_valid is None or now - self.last_valid > dt + 0.001:
            # Never accumulate a missing interval as contact or retreat.
            dt = 0.0
        self.last_valid = now
        fresh = evidence.mouth_source in ('face landmarks', 'pose landmarks')
        away = evidence.kind == 'NONE' and evidence.distance >= 0.18 and fresh
        contact = evidence.kind in ('DIRECT', 'REGISTERED', 'UNCERTAIN', 'OCCLUDED')
        if self.started is not None and now - self.started > 15.0:
            self.reset()
            self.last_at = now
            self.label = 'Sequence timed out - show the vessel away first'
            return None
        if self.phase == 'WAIT':
            if away:
                self.away_time += dt
                self.peak_distance = max(self.peak_distance, evidence.distance)
                if self.away_time >= 0.4:
                    self.phase, self.started = 'ARMED', now
            else:
                self.away_time = 0.0
            self.label = 'Watching approach' if self.phase == 'ARMED' else 'Show the vessel away from your mouth first'
        elif self.phase == 'ARMED':
            if away:
                self.peak_distance = max(self.peak_distance, evidence.distance)
            if contact and self.peak_distance - evidence.distance >= 0.12:
                self.phase = 'CONTACT'
            self.label = 'Possible contact - waiting for sustained evidence' if self.phase == 'CONTACT' else 'Watching approach'
        elif self.phase == 'CONTACT':
            if contact:
                self.contact_time += dt
                if fresh:
                    self.fresh_time += dt
                self.retreat_time = 0.0
                self.label = f'Contact {self.contact_time:.1f}s - lower the vessel when finished'
            elif away:
                if self.contact_time >= 1.2 and self.fresh_time >= 0.6:
                    self.retreat_time += dt
                    self.label = 'Checking completed drinking motion'
                    if self.retreat_time >= 0.5:
                        self.cooldown(now)
                        self.label = 'Likely sip recorded - U to undo'
                        return 'AUTO_SIP'
                else:
                    self.reset()
                    self.last_at = now
                    self.label = 'Contact too brief or unclear - not recorded'
            else:
                # A clear non-contact observation ends the hold, even before away threshold.
                if self.contact_time < 1.2 or self.fresh_time < 0.6:
                    self.reset()
                    self.last_at = now
                self.retreat_time = 0.0
                self.label = 'Unclear motion - not recorded; W if you drank'
        if evidence.kind == 'STRAW':
            self.reset()
            self.last_at = now
            self.label = 'Straw-like cue only - W if you drank'
        return None
