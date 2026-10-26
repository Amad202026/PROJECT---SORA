import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch, MagicMock
from contextlib import ExitStack
import numpy as np
from timer_settings import DEFAULTS,load_settings
from wellness_timers import WellnessTimers


class Log:
    def __init__(self,*args):self.events=[];self.path='in-memory'
    def write(self,name,**data):self.events.append((name,data))


class TimersTests(unittest.TestCase):
    def setUp(self):
        self.cfg=deepcopy(DEFAULTS)
        for key in ('water','movement','eyes','sleep'):self.cfg[key]['interval_seconds']=10
        self.cfg['break_seconds']=3;self.cfg['snooze_seconds']=3
        self.log=Log();self.e=WellnessTimers(self.cfg,self.log);self.t=0
        self.e.update(0,True)
    def advance(self,n,**kwargs):
        values={'present':True};values.update(kwargs)
        for _ in range(n):self.t+=1;self.e.update(self.t,**values)
    def test_presence_counts_work_time_water_counts_absence(self):
        self.advance(5);self.advance(4,present=False)
        self.assertEqual(self.e.timers['sleep'].elapsed,5)
        self.assertEqual(self.e.timers['water'].elapsed,9)
        self.assertEqual(self.e.observed,5)
    def test_resume_does_not_credit_absent_interval(self):
        self.advance(4,present=False);self.advance(1)
        self.assertEqual(self.e.observed,0)
        self.advance(1);self.assertEqual(self.e.observed,1)
    def test_pause_and_calibration_stop_all_timers(self):
        self.advance(5);self.advance(10,paused=True);self.advance(5,calibrating=True)
        for timer in self.e.timers.values():self.assertEqual(timer.elapsed,5)
        self.assertIsNone(self.e.notice())
    def test_long_processing_gap_not_counted(self):
        self.advance(2);self.e.update(1000,True)
        self.assertEqual(self.e.timers['water'].elapsed,2)
        self.assertEqual(self.e.observed,2)
    def test_due_priority_and_dismiss_not_reset(self):
        self.advance(11);self.assertEqual(self.e.notice()[0],'sleep')
        self.e.dismiss('sleep');self.assertEqual(self.e.notice()[0],'eyes')
        self.assertEqual(self.e.timers['sleep'].elapsed,11)
    def test_dismissal_survives_presence_flicker(self):
        self.advance(11)
        for key in self.e.timers:self.e.dismiss(key)
        self.advance(3,present=False);self.advance(3)
        self.assertIsNone(self.e.notice())
    def test_snooze_reappears_without_timer_reset(self):
        self.advance(11);self.e.snooze('sleep')
        self.assertNotEqual(self.e.notice()[0],'sleep')
        self.advance(3);self.assertEqual(self.e.notice()[0],'sleep')
        self.assertEqual(self.e.timers['sleep'].elapsed,14)
    def test_drink_report_early_resets_water_only(self):
        self.advance(5);self.e.handle_key(ord('w'))
        self.assertEqual(self.e.timers['water'].elapsed,0)
        self.assertEqual(self.e.timers['sleep'].elapsed,5)
    def test_manual_movement_is_not_an_eye_break(self):
        self.advance(5);self.e.handle_key(ord('m'))
        self.assertEqual(self.e.timers['movement'].elapsed,0)
        self.assertEqual(self.e.timers['eyes'].elapsed,5)
    def test_break_stops_work_counters_but_water_keeps_time(self):
        self.advance(5);self.e.start_break();self.advance(4,present=False)
        self.assertTrue(self.e.break_complete)
        self.assertEqual(self.e.notice()[0],'break_done')
        self.assertEqual(self.e.timers['sleep'].elapsed,5)
        self.assertEqual(self.e.timers['water'].elapsed,9)
        self.assertEqual(self.e.timers['eyes'].elapsed,5)
        self.e.resume_break()
        self.assertEqual(self.e.timers['eyes'].elapsed,0)
        self.assertEqual(self.e.timers['movement'].elapsed,0)
        self.assertEqual(self.e.timers['sleep'].elapsed,5)
    def test_incomplete_break_does_not_reset_work_timers(self):
        self.advance(5);self.e.start_break();self.advance(1);self.e.resume_break()
        self.assertEqual(self.e.timers['eyes'].elapsed,5)
    def test_pause_freezes_break_countdown(self):
        self.e.start_break();self.advance(10,paused=True)
        self.assertEqual(self.e.break_elapsed,0)
    def test_disabled_feature_stops_and_restarts_fresh(self):
        self.advance(5);self.e.toggle('eyes');self.advance(10)
        self.assertEqual(self.e.timers['eyes'].elapsed,0)
        self.e.toggle('eyes');self.assertEqual(self.e.timers['eyes'].elapsed,0)
    def test_dark_camera_stops_work_and_has_one_dismissible_notice(self):
        self.advance(6,brightness=5)
        self.assertTrue(self.e.dark);self.assertEqual(self.e.observed,0)
        self.assertEqual(self.e.notice()[0],'dark_camera')
        self.e.dismiss('dark_camera');self.advance(5,brightness=5)
        self.assertIsNone(self.e.notice())
        self.advance(3,brightness=100);self.assertFalse(self.e.dark)
    def test_camera_notice_disabled_does_not_disable_quality_gate(self):
        self.e.toggle('dark_camera');self.advance(6,brightness=0)
        self.assertIsNone(self.e.notice());self.assertEqual(self.e.observed,0)
    def test_new_session_resets_sleep(self):
        self.advance(11);other=WellnessTimers(self.cfg,Log())
        self.assertEqual(other.timers['sleep'].elapsed,0)
    def test_posture_dismiss_persists_until_recovery(self):
        self.e.set_posture(True);self.assertEqual(self.e.notice()[0],'posture')
        self.e.dismiss('posture');self.e.set_posture(True);self.assertIsNone(self.e.notice())
        self.e.set_posture(False);self.e.set_posture(True)
        self.assertEqual(self.e.notice()[0],'posture')
    def test_missing_person_never_marks_rest_completed(self):
        self.advance(5);self.advance(10,present=False)
        self.assertEqual(self.e.timers['eyes'].elapsed,5)
        self.assertFalse(self.e.in_break)
    def test_due_logged_once_per_cycle(self):
        self.advance(30)
        events=[d for n,d in self.log.events if n=='timer_due' and d['kind']=='water']
        self.assertEqual(len(events),1)


class SettingsTests(unittest.TestCase):
    def test_demo_retains_disabled_features(self):
        p=MagicMock();p.exists.return_value=True;p.read_text.return_value='{"sleep":{"enabled":false}}'
        cfg=load_settings(p,True)
        self.assertEqual(cfg['eyes']['interval_seconds'],120)
        self.assertFalse(cfg['sleep']['enabled'])
    def test_bad_values_rejected(self):
        for text in ['{"break_seconds":0}','{"sleep":{"enabled":"yes"}}','{"eyes":{"interval_seconds":NaN}}','{"unknown":2}','[]']:
            p=MagicMock();p.exists.return_value=True;p.read_text.return_value=text
            with self.assertRaises(ValueError):load_settings(p)
    def test_packaged_settings_load(self):
        config=load_settings(Path(__file__).parent/'settings.json')
        self.assertEqual(config['sleep']['interval_seconds'],86400)
        self.assertEqual(config['posture']['window_seconds'],1200)


class IntegrationTests(unittest.TestCase):
    def test_real_person_model_runs_without_drinking_models(self):
        from vendor.mp_persondet import MPPersonDet
        root=Path(__file__).parent
        detector=MPPersonDet(str(root/'models/person_detection_mediapipe_2023mar.onnx'))
        self.assertEqual(len(detector.infer(np.zeros((480,640,3),np.uint8))),0)
    def test_main_without_drink_models_and_repeated_popup_rebuilds(self):
        import pose_test,sys
        class Camera:
            released=False
            def __init__(self,*args):pass
            def isOpened(self):return True
            def set(self,*args):pass
            def read(self):return True,np.full((480,640,3),120,np.uint8)
            def release(self):Camera.released=True
        class Person:
            def __init__(self,**kwargs):pass
            def infer(self,frame):return [np.zeros(13)]
        class Pose:
            def __init__(self,**kwargs):pass
            def infer(self,frame,person):return None
        class Popup:
            instance=None
            def __init__(self,engine):self.engine=engine;self.hidden=0;self.closed=False;Popup.instance=self
            def hide(self):self.hidden+=1
            def pump(self):pass
            def close(self):self.closed=True
        with ExitStack() as stack:
            stack.enter_context(patch.object(sys,'argv',['pose_test.py','--demo']))
            for name,value in [('MPPersonDet',Person),('MPPose',Pose),('EventLogger',Log),('DesktopReminder',Popup)]:stack.enter_context(patch.object(pose_test,name,value))
            stack.enter_context(patch('cv2.VideoCapture',Camera))
            for name in ['namedWindow','resizeWindow','imshow','destroyAllWindows']:stack.enter_context(patch('cv2.'+name))
            stack.enter_context(patch('cv2.getWindowProperty',return_value=1))
            stack.enter_context(patch('cv2.waitKey',side_effect=[ord('w'),ord('m'),ord('q')]))
            pose_test.main()
        self.assertTrue(Camera.released);self.assertTrue(Popup.instance.closed)
        self.assertEqual(Popup.instance.hidden,0)
        self.assertTrue(any(n=='timer_reset' and d['source']=='user_reported_drink' for n,d in Popup.instance.engine.logger.events))


class PopupTests(unittest.TestCase):
    def make(self):
        import timer_ui
        config=deepcopy(DEFAULTS);config['water']['interval_seconds']=1
        engine=WellnessTimers(config,Log())
        stack=ExitStack()
        for name in ('Tk','Label','Frame','Button'):stack.enter_context(patch.object(timer_ui.tk,name))
        ui=timer_ui.ReminderCenter(engine)
        ui.root.winfo_reqwidth.return_value=520;ui.root.winfo_reqheight.return_value=240
        ui.root.winfo_screenwidth.return_value=1920;ui.root.winfo_screenheight.return_value=1080
        self.addCleanup(stack.close)
        return ui,engine
    def test_same_notice_does_not_repeat_popup(self):
        ui,e=self.make();e.update(0,True);e.update(1,True)
        for _ in range(20):ui.pump()
        self.assertEqual(ui.root.deiconify.call_count,1)
        self.assertEqual(len([n for n,d in e.logger.events if n=='notice_shown']),1)
    def test_dismiss_does_not_reset_water(self):
        ui,e=self.make();e.update(0,True);e.update(1,True);ui.pump();ui.dismiss();ui.pump()
        self.assertIsNone(ui.visible_key);self.assertEqual(e.timers['water'].elapsed,1)
    def test_popup_drink_action_resets_without_visual_claim(self):
        ui,e=self.make();e.update(0,True);e.update(1,True);ui.pump();ui.act('drink','water')
        self.assertEqual(e.timers['water'].elapsed,0)
        self.assertTrue(any(n=='timer_reset' and d['source']=='user_reported_drink' for n,d in e.logger.events))


if __name__=='__main__':unittest.main()
