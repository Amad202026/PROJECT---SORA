from pathlib import Path
import time

from drink_vision import DrinkVision
from drink_state import HydrationClock
from drink_cycle import DrinkCycle


class HydrationMonitor:
    def __init__(self, root, logger, interval=3600.0):
        self.logger = logger
        self.vision = DrinkVision(Path(root) / 'models/object_detection_nanodet_2022nov.onnx')
        self.sequence = DrinkCycle()
        self.clock = HydrationClock(interval)
        self.pending = None
        self.pending_serial = 0
        self.next_inference = 0.0
        self.present = False
        self.paused = False
        self.status = 'Show a bottle or cup to the camera'
        self.last_evidence = None
        self.last_evidence_key = None
        self.message_until = 0.0
        self.message = ''
        self.was_due = False

    def update(self, frame, landmarks, present, paused, now):
        self.present, self.paused = present, paused
        self.clock.update(now, present, paused)
        if self.clock.due and not self.was_due:
            self.logger.write('water_reminder_due', elapsed_seconds=round(self.clock.elapsed, 1),
                              interval_seconds=self.clock.interval)
        self.was_due = self.clock.due
        if self.pending is not None and now > self.pending['expires']:
            self.logger.write('sip_confirmation_expired', candidate=self.pending['id'])
            self.pending = None
        if paused:
            self.sequence.reset()
            self.vision.clear()
            self.pending = None
            self.status = 'Paused'
            self.last_evidence = None
            return
        self.vision.track_registered(frame, now)
        if now < self.next_inference:
            return
        # Always use a new inference on this frame; never accumulate repeated cached boxes.
        evidence = self.vision.observe(frame, landmarks, now, present)
        self.next_inference = now + 0.2
        self.last_evidence = evidence
        key = (evidence.valid, evidence.track_id, evidence.kind, evidence.mouth_source)
        if key != self.last_evidence_key:
            self.logger.write('drinking_evidence_changed', kind=evidence.kind,
                valid=evidence.valid, track_id=evidence.track_id, vessel=evidence.label,
                object_score=round(evidence.score, 3), hand_near=evidence.hand_near,
                straw_like_line=evidence.straw_line, reason=evidence.reason,
                mouth_source=evidence.mouth_source, vessel_source=evidence.vessel_source)
            self.last_evidence_key = key
        if not present:
            self.pending = None
        event = self.sequence.update(evidence, now)
        self.status = self.sequence.label
        if event == 'AUTO_SIP':
            self.record('automatic_gesture', now)

    def record(self, source='manual_confirmation', now=None):
        now = time.perf_counter() if now is None else now
        self.clock.record(now, source)
        self.pending = None
        self.sequence.cooldown(now)
        self.message = 'Likely sip recorded - U: undo (30s)' if source == 'automatic_gesture' else 'Drink confirmed by you - timer reset'
        self.message_until = now + 8
        self.logger.write('drink_recorded', source=source, count=self.clock.count,
            vessel=self.last_evidence.label if self.last_evidence else None,
            note='Gesture estimate or user report; volume and swallowing not measured')

    def reject(self):
        if self.pending is not None:
            self.logger.write('sip_confirmation_rejected', candidate=self.pending['id'])
        self.pending = None
        self.sequence.cooldown(time.perf_counter())

    def undo(self):
        now = time.perf_counter()
        if self.clock.undo(now):
            self.sequence.cooldown(now)
            self.message, self.message_until = 'Automatic sip undone - previous timer restored', now + 8
            self.logger.write('automatic_sip_undone', count=self.clock.count)

    def handle_key(self, key):
        if key in (ord('w'), ord('W')):
            self.record('manual_confirmation')
        elif key in (ord('n'), ord('N')):
            self.reject()
        elif key in (ord('u'), ord('U')):
            self.undo()

    def panel_lines(self, now):
        elapsed = int(self.clock.elapsed)
        minutes, seconds = divmod(elapsed, 60)
        hours, minutes = divmod(minutes, 60)
        remaining = max(0, int(self.clock.interval - self.clock.elapsed))
        message = self.message if now < self.message_until else self.status
        if self.vision.detections:
            vessels = ', '.join(sorted({v['label'] for v in self.vision.detections}))
            diagnostic = f'Container: {vessels} | Mouth: {self.vision.mouth_source}'
        else:
            diagnostic = f'Container: not detected | Mouth: {self.vision.mouth_source}'
        return [
            f'Water: {hours:02}:{minutes:02}:{seconds:02} since last record | due in {remaining}s',
            diagnostic,
            f'Drinking: {message}',
            f'Recorded drinking events: {self.clock.count} (not volume)',
            'W: I drank   U: undo automatic sip   No sip-question popups',
            self.vision.registered.message if self.vision.registered.tracker is not None else 'Auto vessel tracking enabled | R: select vessel   X: clear',
        ]
