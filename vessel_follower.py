"""Follow one detected vessel, with bounded recovery after a tracking gap."""
import numpy as np
from registered_vessel import RegisteredVessel

def overlap(a,b):
    a,b=np.asarray(a),np.asarray(b)
    inter=np.maximum(0,np.minimum(a[2:],b[2:])-np.maximum(a[:2],b[:2])).prod()
    union=(a[2:]-a[:2]).prod()+(b[2:]-b[:2]).prod()-inter
    return float(inter/union) if union>0 else 0.

class VesselFollower:
    def __init__(self):
        self.tracker=RegisteredVessel(max_gap=2.5);self.identity=0
        self.current=None;self.last_box=None;self.label='vessel';self.model_score=0.
        self.refreshed=self.last_model=self.last_seen=-999.
        self.challenger=None;self.challenger_at=-999.

    def clear(self):
        self.tracker.clear();self.current=None;self.last_box=None
        self.last_model=self.last_seen=-999.;self.challenger=None

    def update(self,frame,now):
        self.current=self.tracker.update(frame,now)
        if self.current is not None:
            self.current.update(label=self.label,source='tracked_model',identity=1000000+self.identity,
                                tracking_score=self.current['score'],score=self.model_score)
            self.last_box=self.current['box'].copy();self.last_seen=now
        if now-self.last_model>5:self.clear()

    def matches(self,detection,box):
        # Cup/glass labels can alternate, but a bottle must remain a bottle.
        same=(detection['label']==self.label or {detection['label'],self.label}<={'cup','glass'})
        return same and box is not None and overlap(detection['box'],box)>=.20

    @staticmethod
    def priority(detection,mouth,scale):
        if mouth is None:return detection['score']
        b=detection['box'];distance=np.linalg.norm((b[:2]+b[2:])/2-np.asarray(mouth))/max(1,scale)
        return detection['score']-.30*min(distance,4)

    def reconcile(self,detections,frame,now,allow_start=True,mouth=None,scale=1):
        candidates=[d for d in detections if d['score']>=.35]
        reference=self.current['box'] if self.current else self.last_box
        matched=[d for d in candidates if self.matches(d,reference)]
        if matched and (self.current is not None or now-self.last_seen<=1.2):
            best=max(matched,key=lambda d:overlap(d['box'],reference)+d['score'])
            self.last_model=now
            if self.current is None or now-self.refreshed>=.8:
                self.seed(best,frame,now,False)
        if not allow_start:return self.current
        if candidates:
            best=max(candidates,key=lambda d:self.priority(d,mouth,scale))
            if self.current is None:
                self.seed(best,frame,now,True)
            elif not self.matches(best,self.current['box']):
                gain=self.priority(best,mouth,scale)-self.priority(self.current,mouth,scale)
                # Require two successive model observations before changing vessels.
                if gain>.18:
                    if self.challenger is not None and now-self.challenger_at<2 and overlap(best['box'],self.challenger)>.20:
                        self.seed(best,frame,now,True);self.challenger=None
                    else:self.challenger=best['box'].copy();self.challenger_at=now
                else:self.challenger=None
            else:self.challenger=None
        return self.current

    def seed(self,detection,frame,now,new_identity):
        box=np.asarray(detection['box'],float)
        roi=tuple(map(int,np.r_[box[:2],box[2:]-box[:2]]))
        if not self.tracker.register(frame,roi,now):return
        if new_identity:self.identity+=1
        self.label=detection['label'];self.model_score=detection['score'];self.refreshed=self.last_model=self.last_seen=now
        self.last_box=box.copy()
        self.current=dict(detection,box=box.copy(),source='tracked_model',identity=1000000+self.identity)
