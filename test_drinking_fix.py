import unittest
from unittest.mock import patch
import numpy as np
import cv2

from hydration import HydrationMonitor
from drink_vision import DrinkEvidence, DrinkVision
from registered_vessel import RegisteredVessel

class NoFace:
    multiple = False
    def observe(self, frame): return None

from pose_tracking import infer_landmarks


class Log:
    def write(self, *args, **kwargs):
        pass


class DecouplingTests(unittest.TestCase):
    def test_detection_still_runs_without_pose_or_person(self):
        class Vision:
            def __init__(self, *args): self.calls = []
            def observe(self, frame, landmarks, now, present):
                self.calls.append((landmarks, present))
                return DrinkEvidence(reason='Container detected; mouth unavailable')
            def track_registered(self, frame, now): pass
            def clear(self): pass
        with patch('hydration.DrinkVision', Vision):
            monitor = HydrationMonitor('.', Log())
        monitor.update(None, None, True, False, 0)
        monitor.update(None, None, False, False, 1)
        self.assertEqual(monitor.vision.calls, [(None, True), (None, False)])
        self.assertEqual(monitor.clock.count, 0)
        self.assertIn('mouth unavailable', monitor.status)

    def make_vision(self):
        vision = DrinkVision.__new__(DrinkVision)
        vision.tracks, vision.next_track = {}, 0
        vision.pose_context = None
        vision.registered = RegisteredVessel()
        from test_drinking import NoFollower
        vision.follower = NoFollower()
        vision.registration_generation = 0
        vision.registered_at = None
        vision.registered_detection = None
        vision.face_anchor = NoFace()
        class Detector:
            def detect(self, frame):
                return [{'box': np.array([300,150,390,240],float), 'label':'cup','score':0.8}]
        vision.detector = Detector()
        return vision

    def test_no_pose_still_draws_container(self):
        vision = self.make_vision()
        evidence = vision.observe(np.zeros((480,640,3),np.uint8), None, 0)
        self.assertEqual(len(vision.detections), 1)
        self.assertFalse(evidence.valid)
        self.assertIn('mouth unavailable', evidence.reason)

    def test_recent_context_expires_and_never_means_direct_contact(self):
        vision = self.make_vision()
        frame = np.zeros((480,640,3),np.uint8)
        vision.pose_context = (0, np.array([320,150],float), 200)
        evidence = vision.observe(frame, None, 0.2)
        self.assertEqual(evidence.kind, 'OCCLUDED')
        self.assertEqual(evidence.mouth_source, 'recent mouth reference')
        evidence = vision.observe(frame, None, 3.1)
        self.assertFalse(evidence.valid)

    def test_context_cleared_when_no_single_person(self):
        vision = self.make_vision()
        vision.pose_context = (0, np.array([320,150],float), 200)
        result = vision.observe(np.zeros((480,640,3),np.uint8), None, 0.1, False)
        self.assertIsNone(vision.pose_context)
        self.assertFalse(result.valid)

class MirrorRecoveryTests(unittest.TestCase):
    def test_mirrored_retry_restores_coordinates(self):
        frame = np.zeros((480,640,3),np.uint8)
        people = [np.zeros(13)]
        points = np.zeros((39,5))
        points[:,3:] = 1
        points[0,0] = 200
        points[11,0] = 100
        points[12,0] = 300
        class Detector:
            def infer(self, frame): return people
        class Pose:
            calls = 0
            def infer(self, frame, person):
                self.calls += 1
                return None if self.calls == 1 else [None,points]
        restored, source = infer_landmarks(frame, people, Detector(), Pose())
        self.assertEqual(source, 'mirrored recovery')
        self.assertEqual(restored[0,0], 439)
        self.assertEqual(restored[11,0], 339)
        self.assertEqual(restored[12,0], 539)
        self.assertEqual(points[0,0], 200)


class RegistrationTests(unittest.TestCase):
    def pattern(self):
        frame = np.zeros((240,320,3),np.uint8)
        for x in range(100,180,12):
            for y in range(70,150,12):
                cv2.rectangle(frame,(x,y),(x+5,y+5),(255,255,255),-1)
        return frame

    def test_registration_tracks_translation_then_expires(self):
        tracker = RegisteredVessel()
        frame = self.pattern()
        self.assertTrue(tracker.register(frame,(90,60,100,110),0))
        moved = cv2.warpAffine(frame,np.array([[1,0,4],[0,1,3]],dtype=float),(320,240))
        detection = tracker.update(moved,0.2)
        self.assertIsNotNone(detection)
        self.assertEqual(detection['source'],'registered')
        from drink_vision import iou
        self.assertGreater(iou(detection['box'], np.array([94,63,194,173])), 0.6)
        self.assertIsNone(tracker.update(moved,2))

    def test_blank_roi_is_not_registered(self):
        tracker = RegisteredVessel()
        self.assertFalse(tracker.register(np.zeros((240,320,3),np.uint8),(50,50,100,100),0))

    def test_lost_target_does_not_keep_last_box(self):
        tracker = RegisteredVessel()
        frame = self.pattern()
        self.assertTrue(tracker.register(frame,(90,60,100,110),0))
        self.assertIsNone(tracker.update(np.zeros_like(frame),0.2))
        self.assertIsNone(tracker.box)


if __name__ == '__main__':
    unittest.main()
