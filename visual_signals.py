"""Timed, conservative visual cues; missing evidence never means recovery."""
import statistics


class VisualSignals:
    def __init__(self, config, logger):
        self.config=config; self.logger=logger; self.reference=None; self.samples=[]
        self.reset_session()

    def reset_session(self):
        self.previous=None; self.previous_valid=False
        self.close_seconds=self.recovery_seconds=self.closed_seconds=0.
        self.distance='Calibration required'; self.fatigue='Waiting for observation'
        self.distance_active=False; self.fatigue_active=False; self.fatigue_fired=False
        self.generation={'distance':0,'fatigue':0}; self.dismissed=set(); self.snoozed={}

    def begin_calibration(self):
        self.reference=None; self.samples=[]; self.interrupt()

    def sample(self, face):
        if face and face['frontal'] and face['ear']>.12:
            self.samples.append((face['span'],face['ear']))

    def finish_calibration(self):
        if len(self.samples)>=8:
            spans, ears=zip(*self.samples)
            self.reference={'span':statistics.median(spans), 'ear':statistics.median(ears)}
            self.logger.write('face_reference_saved',sample_count=len(self.samples))
        else:
            self.logger.write('face_reference_unavailable',sample_count=len(self.samples))

    def interrupt(self):
        self.previous=None; self.previous_valid=False
        self.close_seconds=self.recovery_seconds=self.closed_seconds=0.
        self.distance='Not observed'; self.fatigue='Not observed'

    def update(self, face, now, observed, usable=True, drinking=False):
        dt=0 if self.previous is None else now-self.previous
        dt=dt if 0<=dt<=1 else 0
        valid=bool(usable and face and face['frontal'] and self.reference and not drinking)
        if not valid or not self.previous_valid:dt=0
        self.previous=now; self.previous_valid=valid
        if not valid:
            self.close_seconds=self.recovery_seconds=self.closed_seconds=0.
            self.distance='Calibration required' if not self.reference else 'Not observed'
            self.fatigue='Calibration required' if not self.reference else 'Not observed'
            return
        ratio=face['span']/self.reference['span']
        self.distance='Closer' if ratio>=self.config['distance']['size_ratio'] else 'Near reference'
        if ratio>=self.config['distance']['size_ratio']:
            self.close_seconds+=dt; self.recovery_seconds=0
            if self.config['distance']['enabled'] and self.close_seconds>=self.config['distance']['hold_seconds'] and not self.distance_active:
                self.distance_active=True;self.generation['distance']+=1;self.dismissed.discard('distance')
                self.logger.write('distance_reminder',relative_face_size=round(ratio,2))
        elif ratio<1.12:
            self.close_seconds=0;self.recovery_seconds+=dt
            if self.recovery_seconds>=3 and self.distance_active:
                self.distance_active=False;self.dismissed.discard('distance');self.snoozed.pop('distance',None)
                self.logger.write('distance_recovered')
        else:self.close_seconds=self.recovery_seconds=0
        warm=observed>=self.config['fatigue']['warmup_seconds']
        self.fatigue='Already notified' if self.fatigue_fired else 'Watching eye closure' if warm else 'Warming up'
        # Bilateral closure required; ordinary blinks do not reach this duration.
        if warm and face['ear']<self.reference['ear']*.55:
            self.closed_seconds+=dt
        else:self.closed_seconds=0
        if self.config['fatigue']['enabled'] and self.closed_seconds>=self.config['fatigue']['closure_seconds'] and not self.fatigue_fired:
            self.fatigue_active=self.fatigue_fired=True;self.generation['fatigue']+=1
            self.logger.write('prolonged_eye_closure',seconds=round(self.closed_seconds,2),diagnosis=False)

    def notice(self, now):
        if not self.previous_valid:return None
        for kind in ('fatigue','distance'):
            if self.config[kind]['enabled'] and getattr(self,kind+'_active') and kind not in self.dismissed and now>=self.snoozed.get(kind,0):
                return kind,self.generation[kind]
        return None

    def dismiss(self, kind):self.dismissed.add(kind)
    def snooze(self, kind, now):self.snoozed[kind]=now+self.config['snooze_seconds']
