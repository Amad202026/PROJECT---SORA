"""A stable identity across model detections and current-frame tracking."""
import numpy as np
from registered_vessel import RegisteredVessel


def overlap(a,b):
    inter=np.maximum(0,np.minimum(a[2:],b[2:])-np.maximum(a[:2],b[:2])).prod()
    union=(a[2:]-a[:2]).prod()+(b[2:]-b[:2]).prod()-inter
    return float(inter/union) if union>0 else 0.0


class VesselFollower:
    def __init__(self):
        self.tracker=RegisteredVessel()
        self.identity=0
        self.current=None
        self.label='vessel'
        self.refreshed=-999.0
        self.last_model=-999.0

    def clear(self):
        self.tracker.clear()
        self.current=None
        self.last_model=-999.0

    def update(self,frame,now):
        self.current=self.tracker.update(frame,now)
        if self.current is not None:
            self.current.update(label=self.label,source='tracked_model',identity=1000000+self.identity)
        # Prevent a drifting box from becoming perpetual semantic evidence.
        if now-self.last_model>8:
            self.clear()

    def reconcile(self,detections,frame,now,allow_start=True):
        candidates=[d for d in detections if d['score']>=.35]
        if self.current is not None:
            matched=[d for d in candidates if d['label']==self.label and overlap(d['box'],self.current['box'])>=.25]
            if matched:
                best=max(matched,key=lambda d:d['score'])
                self.last_model=now
                if now-self.refreshed>=.8:
                    self.seed(best,frame,now,new_identity=False)
            return self.current
        # A lost identity cannot silently inherit a different vessel.
        if allow_start and candidates:
            self.seed(max(candidates,key=lambda d:d['score']),frame,now,new_identity=True)
        return self.current

    def seed(self,detection,frame,now,new_identity):
        box=detection['box']
        roi=tuple(map(int,np.r_[box[:2],box[2:]-box[:2]]))
        if not self.tracker.register(frame,roi,now):return
        if new_identity:self.identity+=1
        self.label=detection['label']
        self.refreshed=self.last_model=now
        self.current=dict(detection,source='tracked_model',identity=1000000+self.identity)
