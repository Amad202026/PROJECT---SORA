"""Conservative temporal observations; not gaze, sleep, or medical diagnosis."""


class ObservationExtras:
    def __init__(self, logger):
        self.logger=logger;self.previous=None;self.previous_absent=False
        self.away=0.;self.returned=0.;self.completed_away=False
        self.orientation='Not observed';self.yawn_hold=0.;self.yawn_started=None
        self.yawns=[];self.last_yawn=-999;self.last_open=False

    def reset_boundary(self):
        self.previous=None;self.previous_absent=False;self.away=0.;self.returned=0.
        self.completed_away=False;self.yawn_hold=0.;self.yawn_started=None;self.last_open=False

    def update(self, face, now, people, bright, running, drinking=False):
        dt=0 if self.previous is None else now-self.previous
        if not 0<=dt<=1:self.reset_boundary();dt=0
        self.previous=now
        if not running or not bright:
            self.reset_boundary();self.orientation='Not observed';return False
        self.orientation=('Facing camera' if face['frontal'] else 'Turned from camera') if face else 'Not observed'
        absent=people==0 and face is None
        if absent:
            if self.previous_absent:self.away+=dt
            self.returned=0
            if self.away>=60:self.completed_away=True
        elif people==1 and face is not None:
            self.returned+=dt
            if self.returned>=2 and self.completed_away:
                self.logger.write('away_interval_observed',seconds=round(self.away,1),verified_stretch=False,verified_sleep=False)
                self.away=0;self.completed_away=False;self.previous_absent=False
                return True
            if self.returned>=2:self.away=0
        else:
            # Ambiguous tracking / another person cannot complete an away cycle.
            self.away=0;self.completed_away=False;self.returned=0
        self.previous_absent=absent
        opening=bool(face and face['frontal'] and not drinking and face.get('mouth_open_ratio',0)>.60)
        if opening:
            if self.last_open:self.yawn_hold+=dt
            if self.yawn_started is None:self.yawn_started=now
        else:
            if self.last_open and 2<=self.yawn_hold<=8 and face and face['frontal'] and not drinking and now-self.last_yawn>=10:
                self.yawns.append(now);self.last_yawn=now
                self.logger.write('possible_yawn',seconds=round(self.yawn_hold,1),diagnosis=False)
            self.yawn_hold=0;self.yawn_started=None
        self.last_open=opening;self.yawns=[t for t in self.yawns if now-t<=120]
        return False
