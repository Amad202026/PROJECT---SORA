import unittest
from unittest.mock import patch
import numpy as np
from registered_vessel import RegisteredVessel
from pose_quality import pose_is_plausible
from face_anchor import FaceAnchor
import test_drinking_fix as fixtures
from hydration import HydrationMonitor
from drink_vision import DrinkEvidence


class TrackingTests(unittest.TestCase):
    def test_low_score_never_reuses_box_and_short_occlusion_can_recover(self):
        class Tracker:
            score = 0.9
            def init(self, *args): pass
            def update(self, frame): return True, (90,60,100,110)
            def getTrackingScore(self): return self.score
        fake=Tracker()
        tracker=RegisteredVessel(factory=lambda params: fake)
        frame=fixtures.RegistrationTests().pattern()
        tracker.register(frame,(90,60,100,110),0)
        self.assertIsNotNone(tracker.update(frame,.1))
        fake.score=.2
        self.assertIsNone(tracker.update(frame,.2))
        self.assertIsNone(tracker.box)
        fake.score=.8
        self.assertIsNotNone(tracker.update(frame,.3))
        fake.score=.2
        for t in [.4,.9,1.4,1.9,2.0]:
            self.assertIsNone(tracker.update(frame,t))
        self.assertIsNone(tracker.tracker)

    def test_tracker_runs_between_slow_detector_updates(self):
        class Vision:
            def __init__(self,*args): self.tracked=[]; self.observed=[]
            def track_registered(self,frame,now): self.tracked.append(now)
            def observe(self,frame,points,now,present):
                self.observed.append(now)
                return DrinkEvidence()
            def clear(self): pass
        with patch('hydration.DrinkVision',Vision):
            monitor=HydrationMonitor('.',fixtures.Log())
        for now in [0,.05,.1,.15,.21]:
            monitor.update(None,None,True,False,now)
        self.assertEqual(len(monitor.vision.tracked),5)
        self.assertEqual(len(monitor.vision.observed),2)


class GeometryTests(unittest.TestCase):
    def test_false_shoulders_near_neck_rejected(self):
        p=np.zeros((39,5)); p[:,3:]=1
        p[0,:2]=(320,180); p[11,:2]=(310,220); p[12,:2]=(340,240)
        self.assertFalse(pose_is_plausible(p,640,480)[0])
        p[11,:2]=(210,340); p[12,:2]=(430,340)
        self.assertTrue(pose_is_plausible(p,640,480)[0])

    def test_face_anchor_works_without_pose_and_multiple_faces_block(self):
        vision=fixtures.DecouplingTests().make_vision()
        class Face:
            multiple=False
            def observe(self,frame): return np.array([290.,150.]),200.
        vision.face_anchor=Face()
        frame=np.zeros((480,640,3),np.uint8)
        evidence=vision.observe(frame,None,0)
        self.assertTrue(evidence.valid)
        self.assertEqual(evidence.mouth_source,'face landmarks')
        self.assertEqual(evidence.kind,'UNCERTAIN')
        vision.face_anchor.multiple=True
        evidence=vision.observe(frame,None,.2)
        self.assertFalse(evidence.valid)
        self.assertIsNone(vision.pose_context)

    def test_actual_yunet_blank_frame(self):
        anchor=FaceAnchor()
        self.assertIsNone(anchor.observe(np.zeros((480,640,3),np.uint8)))
        self.assertFalse(anchor.multiple)


if __name__=='__main__': unittest.main()
