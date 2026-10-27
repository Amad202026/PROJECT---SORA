"""Local vessel motion estimates; a likely sip is not an ingestion measurement."""
import math
import numpy as np
from vessel_detector import VesselDetector
from vessel_views import VesselViews
from vessel_follower import VesselFollower
from vessel_fallback import VesselFallback
from face_anchor import FaceAnchor
from straw_assist import StrawAssist

class SipSequence:
    def __init__(self):
        self.cooldown_until=0.;self.reset()

    def reset(self):
        self.phase='WAIT';self.identity=None;self.previous=None;self.valid_at=None
        self.away=self.hold=self.retreat=self.fresh_hold=0.;self.started=None
        self.origin=None;self.travel=0.
        self.label='Show a cup or bottle away from your mouth first'

    def update(self,now,identity=None,distance=None,fresh=True,center=None,scale=1):
        gap=0 if self.previous is None else max(0,now-self.previous)
        if gap>2.5:self.reset()
        # Slow inference must not turn a single sample into seconds of contact.
        dt=min(gap,.25);self.previous=now
        if now<self.cooldown_until:
            self.label='Likely sip recorded — lower the vessel';return False
        if identity is None or distance is None:
            if self.valid_at is None or now-self.valid_at>1.2:self.reset();self.previous=now
            self.label='Tracking unclear — no drink recorded';return False
        if identity!=self.identity:
            self.reset();self.identity=identity;self.previous=now;dt=0
        if self.valid_at is None or now-self.valid_at>gap+.01:dt=0
        self.valid_at=now
        if self.started is not None and now-self.started>20:
            self.reset();return False
        if center is not None:
            center=np.asarray(center,float)
            if self.origin is None:self.origin=center.copy()
            self.travel=max(self.travel,float(np.linalg.norm(center-self.origin))/max(1,scale))
        away=distance>.22 and fresh
        contact=distance<.14
        if self.phase=='WAIT':
            self.away=self.away+dt if away else 0
            if self.away>=.30:self.phase='APPROACH';self.started=now
        elif self.phase=='APPROACH':
            # Fresh lips and actual vessel displacement must establish contact.
            if contact and fresh and self.travel>=.15:
                self.phase='CONTACT';self.hold=self.fresh_hold=0
        elif self.phase=='CONTACT':
            if contact:
                self.hold+=dt;self.fresh_hold+=dt if fresh else 0;self.retreat=0
            elif away and self.hold>=.8 and self.fresh_hold>=.25:
                self.retreat+=dt
                if self.retreat>=.35:
                    self.reset();self.cooldown_until=now+10
                    self.label='Likely sip recorded — Undo available';return True
            elif away:self.reset()
            else:
                self.retreat=0
                if self.hold<.8:self.hold=self.fresh_hold=0
        self.label={'WAIT':'Show the vessel away from your mouth',
                    'APPROACH':'Watching the vessel move toward your mouth',
                    'CONTACT':'Contact observed — lower the vessel when finished'}[self.phase]
        return False

class DrinkingAuto:
    def __init__(self,root):
        self.detector=VesselViews(VesselDetector(str(root/'models/object_detection_nanodet_2022nov.onnx'),prob_threshold=.35))
        self.follower=VesselFollower();self.cycle=SipSequence()
        self.fallback=VesselFallback(str(root/'models/object_detection_yolox_2022nov.onnx'),confThreshold=.4)
        self.face_fallback=FaceAnchor()
        self.last_detection=self.last_fallback=-999.
        self.last_face=None;self.face_at=-999.;self.box=None;self.vessel_label='No vessel'
        self.straw=StrawAssist();self.straw_enabled=False;self.straw_contact=False

    @property
    def label(self):return self.vessel_label+' | '+self.cycle.label

    def reset(self):
        self.follower.clear();self.cycle.reset();self.last_face=None;self.face_at=-999.;self.box=None
        self.vessel_label='No vessel';self.straw.reset();self.straw_contact=False

    def update(self,frame,face,now,allowed=True):
        if not allowed:self.reset();return False
        if face is None:
            found=self.face_fallback.observe(frame)
            if self.face_fallback.multiple:self.reset();return False
            if found is not None:face={'mouth':found[0],'scale':found[1]}
        if face is not None:self.last_face=face;self.face_at=now
        # Only bridge an already-established contact. A stale mouth cannot start
        # or finish a sip, and missing vessel tracking never counts as retreat.
        bridge=self.cycle.phase=='CONTACT' and now-self.face_at<=2.5
        anchor=face if face is not None else self.last_face if bridge else None
        self.follower.update(frame,now)
        if now-self.last_detection>=.6:
            detections=self.detector.detect(frame);self.last_detection=now
            current=self.follower.current
            matched=current is not None and any(self.follower.matches(d,current['box']) for d in detections)
            # Do not let a weak NanoDet box suppress the independent bottle detector.
            if now-self.last_fallback>=2 and (not matched or self.cycle.phase!='CONTACT'):
                detections+=self.fallback.detect(frame);self.last_fallback=now
            self.follower.reconcile(detections,frame,now,allow_start=self.cycle.phase!='CONTACT',
                                    mouth=anchor['mouth'] if anchor is not None else None,
                                    scale=anchor['scale'] if anchor is not None else 1)
        item=self.follower.current;self.box=item['box'] if item else None
        self.vessel_label=item['label'].capitalize() if item else 'No vessel'
        if item is None or anchor is None:
            self.straw.reset();self.straw_contact=False
            return self.cycle.update(now)
        x,y=anchor['mouth'];x1,y1,x2,y2=item['box']
        distance=math.hypot(max(x1-x,0,x-x2),max(y1-y,0,y-y2))/max(1,anchor['scale'])
        self.straw_contact=self.straw.observe(frame,face,item['box'],now) if self.straw_enabled else False
        if self.straw_contact:distance=.01
        return self.cycle.update(now,item['identity'],distance,face is not None,
                                 center=((x1+x2)/2,(y1+y2)/2),scale=anchor['scale'])
