"""Run: python -B -m unittest test_drinking -v (no camera or desktop windows)."""
import unittest
from unittest.mock import patch
from pathlib import Path
import numpy as np

from drink_state import HydrationClock
from drink_vision import DrinkEvidence, DrinkVision, VesselDetector
from hydration import HydrationMonitor
from registered_vessel import RegisteredVessel

class NoFollower:
    def update(self, *args): pass
    def reconcile(self, *args, **kwargs): return None
    def clear(self): pass

class NoFace:
    multiple = False
    def observe(self, frame): return None



def evidence(kind='NONE', distance=0.35, track_id=1, valid=True):
    return DrinkEvidence(valid=valid, kind=kind, distance=distance, track_id=track_id,
                         label='cup', score=0.8, hand_near=kind == 'DIRECT')


class ClockTests(unittest.TestCase):
    def test_manual_drink_before_due_resets(self):
        clock = HydrationClock(60)
        clock.update(0, True)
        clock.update(40, True)
        clock.record(40, 'manual_confirmation')
        clock.update(80, True)
        self.assertEqual(clock.elapsed, 40)
        self.assertFalse(clock.due)
        clock.update(100, True)
        self.assertTrue(clock.due)

    def test_paused_time_excluded_absence_defers_popup(self):
        clock = HydrationClock(60)
        clock.update(0, True)
        clock.update(20, True)
        clock.update(20, True, True)
        clock.update(120, True, True)
        clock.update(120, True, False)
        clock.update(130, True)
        self.assertEqual(clock.elapsed, 30)
        clock.update(200, False)
        self.assertFalse(clock.due)
        clock.update(201, True)
        self.assertTrue(clock.due)

    def test_undo_restores_previous_clock(self):
        clock = HydrationClock(60)
        clock.update(0, True)
        clock.update(40, True)
        clock.record(40, 'automatic_gesture')
        clock.update(45, True)
        self.assertTrue(clock.undo(45))
        self.assertEqual(clock.elapsed, 45)
        self.assertEqual(clock.count, 0)
        self.assertFalse(clock.undo(45))

    def test_undo_expired(self):
        clock = HydrationClock()
        clock.record(0, 'automatic_gesture')
        self.assertFalse(clock.undo(31))


class VisionGeometryTests(unittest.TestCase):
    def setUp(self):
        self.vision = DrinkVision.__new__(DrinkVision)
        self.vision.tracks = {}
        self.vision.next_track = 0
        self.vision.registered = RegisteredVessel()
        from vessel_follower import VesselFollower
        self.vision.follower = NoFollower()
        self.vision.registration_generation = 0
        self.vision.registered_at = None
        self.vision.registered_detection = None
        self.vision.face_anchor = NoFace()
        self.vision.pose_context = None
        self.vision.mouth_source = 'unavailable'
        self.frame = np.zeros((480, 640, 3), np.uint8)
        self.points = np.zeros((39, 5), dtype=float)
        self.points[:, 3:] = 1
        for index, coords in {0:(320,130), 2:(300,110), 5:(340,110), 9:(310,150), 10:(330,150), 11:(220,330),
                              12:(420,330), 15:(360,210), 16:(500,400),
                              19:(360,190), 20:(500,400)}.items():
            self.points[index, :2] = coords

    def observe_with_box(self, box):
        class FakeDetector:
            def detect(_, frame):
                return [{'box': np.array(box, dtype=float), 'label':'cup', 'score':0.8}]
        self.vision.detector = FakeDetector()
        return self.vision.observe(self.frame, self.points, 0)

    def test_direct_container_mouth_hand(self):
        result = self.observe_with_box([330,150,410,250])
        self.assertEqual(result.kind, 'DIRECT')

    def test_straw_like_line_only_weak_cue(self):
        import cv2
        cv2.line(self.frame, (320,150), (340,220), (255,255,255), 3)
        result = self.observe_with_box([300,220,390,330])
        self.assertEqual(result.kind, 'STRAW')

    def test_no_line_not_straw(self):
        result = self.observe_with_box([300,220,390,330])
        self.assertEqual(result.kind, 'NONE')

    def test_hidden_mouth_invalid(self):
        self.points[9, 3:] = 0.1
        result = self.observe_with_box([330,150,410,250])
        self.assertFalse(result.valid)


class MonitorTests(unittest.TestCase):
    def test_weak_straw_evidence_never_opens_popup_or_resets_clock(self):
        class FakeVision:
            def __init__(self, *args): pass
            def observe(self, *args): return evidence('STRAW', 0.3)
            def track_registered(self, frame, now): pass
            def clear(self): pass
        class Log:
            def __init__(self): self.events = []
            def write(self, name, **kwargs): self.events.append(name)
        log = Log()
        with patch('hydration.DrinkVision', FakeVision):
            monitor = HydrationMonitor('.', log, 60)
        for n in range(41):
            monitor.update(None, None, True, False, n / 10)
        self.assertIsNone(monitor.pending)
        self.assertEqual(monitor.clock.count, 0)
        self.assertAlmostEqual(monitor.clock.elapsed, 4)
        monitor.record('manual_confirmation', now=4)
        self.assertEqual(monitor.clock.count, 1)
        self.assertEqual(monitor.clock.elapsed, 0)
        self.assertIsNone(monitor.pending)


class ModelSmokeTests(unittest.TestCase):
    def test_actual_nanodet_loads_and_runs_with_opencv5(self):
        root = Path(__file__).resolve().parent
        detector = VesselDetector(str(root / 'models/object_detection_nanodet_2022nov.onnx'))
        output = detector.detect(np.zeros((480,640,3), np.uint8))
        self.assertEqual(output, [])
        # Exercise non-empty NMS and unordered OpenCV 5 tensors as well.
        scores = [np.zeros((1, len(a), 80), np.float32) for a in detector.anchors_mlvl]
        boxes = [np.zeros((1, len(a), 32), np.float32) for a in detector.anchors_mlvl]
        scores[0][0, 1000, 41] = 0.9
        predictions = detector.post_process(scores + boxes)
        self.assertEqual(len(predictions), 1)
        self.assertEqual(int(predictions[0, 5]), 41)


class ApplicationIntegrationTests(unittest.TestCase):
    def test_main_loop_w_key_and_cleanup_without_camera(self):
        import pose_test
        import sys
        class FakeCapture:
            released = False
            def __init__(self, *args): pass
            def isOpened(self): return True
            def set(self, *args): return True
            def read(self): return True, np.zeros((480,640,3), np.uint8)
            def release(self): FakeCapture.released = True
        class Person:
            def __init__(self, **kwargs): pass
            def infer(self, frame): return [np.zeros(13)]
        class Pose:
            def __init__(self, **kwargs): pass
            def infer(self, frame, person):
                landmarks = np.zeros((39,5))
                landmarks[:,3:] = 1
                landmarks[0,:2] = (320,130)
                landmarks[11,:2] = (220,300)
                landmarks[12,:2] = (420,300)
                return [None, landmarks]
        class Logger:
            records = []
            path = 'in-memory-test'
            def __init__(self, *args): pass
            def write(self, name, **data): self.records.append((name,data))
        class Popup:
            closed = False
            def __init__(self, **kwargs): pass
            def show(self): pass
            def hide(self): pass
            def set_hydration(self, **kwargs): pass
            def pump(self): pass
            def close(self): Popup.closed = True
        class Vision:
            def __init__(self, *args):
                self.detections = []
                self.mouth_source = 'unavailable'
                self.registered = RegisteredVessel()
            def observe(self, *args): return evidence(track_id=-1)
            def track_registered(self, frame, now): pass
            def clear(self): pass
            def draw(self, frame): pass
        from contextlib import ExitStack
        with ExitStack() as stack:
            stack.enter_context(patch.object(sys, 'argv', ['pose_test.py', '--demo']))
            for name, value in [('MPPersonDet', Person), ('MPPose', Pose),
                                ('EventLogger', Logger), ('DesktopReminder', Popup)]:
                stack.enter_context(patch.object(pose_test, name, value))
            stack.enter_context(patch('hydration.DrinkVision', Vision))
            stack.enter_context(patch('cv2.VideoCapture', FakeCapture))
            for name in ['namedWindow', 'resizeWindow', 'imshow', 'destroyAllWindows']:
                stack.enter_context(patch('cv2.' + name))
            stack.enter_context(patch('cv2.getWindowProperty', return_value=1))
            stack.enter_context(patch('cv2.waitKey', side_effect=[ord('w'), ord('q')]))
            pose_test.main()
        self.assertTrue(FakeCapture.released)
        self.assertTrue(Popup.closed)
        self.assertTrue(any(name == 'drink_recorded' and data['source'] == 'manual_confirmation'
                            for name, data in Logger.records))
        self.assertTrue(any(name == 'session_closed' for name, _ in Logger.records))


if __name__ == '__main__':
    unittest.main()
