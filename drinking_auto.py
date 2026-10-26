"""Vessel-to-mouth motion estimate. No popup questions; no volume estimate."""
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
        self.cooldown_until=0.; self.reset()

    def reset(self):
        self.phase='WAIT';self.identity=None;self.previous=None;self.valid_at=None
        self.away=self.hold=self.retreat=0.;self.started=None
        self.label='Show a cup or bottle away from your mouth first'

    def update(self, now, identity=None, distance=None, fresh=True):
        dt=0 if self.previous is None else max(0,now-self.previous)
        if dt>1:self.reset();dt=0
        self.previous=now
        if now<self.cooldown_until:
            self.label='Likely sip recorded';return False
        if identity is None or distance is None:
            if self.valid_at is None or now-self.valid_at>.7:self.reset();self.previous=now
            self.label='Tracking unclear — no drink recorded';return False
        if identity!=self.identity:
            self.reset();self.identity=identity;self.previous=now;dt=0
        if self.valid_at is None or now-self.valid_at>dt+.01:dt=0
        self.valid_at=now
        if self.started is not None and now-self.started>20:
            self.reset();return False
        away=distance>.20 and fresh
        contact=distance<.10
        if self.phase=='WAIT':
            self.away=self.away+dt if away else 0
            if self.away>=.35:self.phase='APPROACH';self.started=now
        elif self.phase=='APPROACH':
            if contact:self.phase='CONTACT';self.hold=0
        elif self.phase=='CONTACT':
            if contact:self.hold+=dt;self.retreat=0
            elif away and self.hold>=1.0:
                self.retreat+=dt
                if self.retreat>=.4:
                    self.reset();self.cooldown_until=now+10;self.label='Likely sip recorded';return True
            elif away:self.reset()
            else:self.retreat=0
        self.label={'WAIT':'Show the vessel away from your mouth','APPROACH':'Watching vessel approach','CONTACT':'Contact observed — lower the vessel when finished'}[self.phase]
        return False


class DrinkingAuto:
    def __init__(self,root):
        self.detector=VesselViews(VesselDetector(str(root/'models/object_detection_nanodet_2022nov.onnx'),prob_threshold=.35))
        self.follower=VesselFollower();self.cycle=SipSequence()
        self.fallback=VesselFallback(str(root/'models/object_detection_yolox_2022nov.onnx'),confThreshold=.4)
        self.face_fallback=FaceAnchor()
        self.last_detection=-999;self.last_face=None;self.face_at=-999;self.box=None
        self.straw=StrawAssist();self.straw_enabled=False;self.straw_contact=False

    @property
    def label(self):return self.cycle.label

    def reset(self):
        self.follower.clear();self.cycle.reset();self.last_face=None;self.face_at=-999;self.box=None
        self.straw.reset();self.straw_contact=False

    def update(self,frame,face,now,allowed=True):
        if not allowed:
            self.reset();return False
        if face is None:
            anchor=self.face_fallback.observe(frame)
            if self.face_fallback.multiple:
                self.reset();return False
            if anchor is not None:face={'mouth':anchor[0],'scale':anchor[1]}
        # A short occlusion bridge permits the vessel to cover the lips. Never reuse
        # a mouth indefinitely and never complete a sip until a fresh face returns.
        if face:
            self.last_face=face;self.face_at=now
        anchor=face or (self.last_face if now-self.face_at<=1.5 else None)
        self.follower.update(frame,now)
        if now-self.last_detection>=.7:
            detections=self.detector.detect(frame);self.last_detection=now
            if not detections and self.follower.current is None:detections=self.fallback.detect(frame)
            self.follower.reconcile(detections,frame,now,allow_start=self.cycle.phase=='WAIT')
        item=self.follower.current;self.box=item['box'] if item else None
        if item is None or anchor is None:
            self.straw.reset();self.straw_contact=False
            return self.cycle.update(now)
        x,y=anchor['mouth'];x1,y1,x2,y2=item['box']
        distance=math.hypot(max(x1-x,0,x-x2),max(y1-y,0,y-y2))/max(1,anchor['scale'])
        self.straw_contact=self.straw.observe(frame,face,item['box'],now) if self.straw_enabled else False
        if self.straw_contact:distance=.01
        return self.cycle.update(now,item['identity'],distance,face is not None)
