from copy import deepcopy
from pathlib import Path
import unittest
from drinking_auto import SipSequence
from visual_signals import VisualSignals
from session_controller import SessionController
from timer_settings import DEFAULTS

class VisualFeatureTests(unittest.TestCase):
    def test_drinking_complete_cycle_once(self):
        s=SipSequence();events=[]
        for i in range(60):
            d=.5 if i<10 or i>=35 else .03
            if s.update(i*.1,1,d):events.append(i)
        self.assertEqual(len(events),1)
    def test_missing_contact_does_not_confirm(self):
        s=SipSequence();events=[]
        for i in range(60):
            if 10<=i<35:r=s.update(i*.1)
            else:r=s.update(i*.1,1,.5)
            events.append(r)
        self.assertFalse(any(events))
    def test_static_vessel_at_mouth_never_arms(self):
        s=SipSequence()
        self.assertFalse(any(s.update(i*.1,1,.01) for i in range(100)))
    def test_brief_contact_not_recorded(self):
        s=SipSequence()
        self.assertFalse(any(s.update(i*.1,1,.01 if 10<=i<14 else .5) for i in range(60)))
    def test_identity_change_cancels_sip(self):
        s=SipSequence()
        self.assertFalse(any(s.update(i*.1,1 if i<30 else 2,.01 if 10<=i<30 else .5) for i in range(60)))
    def test_retreat_requires_fresh_face(self):
        s=SipSequence()
        self.assertFalse(any(s.update(i*.1,1,.01 if 10<=i<30 else .5,fresh=i<30) for i in range(60)))
    def setup_signals(self):
        c=SessionController(Path('.'),deepcopy(DEFAULTS),persist=False)
        v=c.signals;v.reference={'span':100.,'ear':.3};return c,v
    def face(self,span=100,ear=.3):return {'span':span,'ear':ear,'frontal':True}
    def test_distance_requires_sustained_change(self):
        c,v=self.setup_signals()
        for i in range(60):v.update(self.face(140 if i<10 else 100),i*.1,100)
        self.assertFalse(v.distance_active)
        for i in range(60,300):v.update(self.face(140),i*.1,100)
        self.assertTrue(v.distance_active)
        v.update(None,30.1,100);self.assertIsNone(v.notice(30.1))
        self.assertTrue(v.distance_active)
        for i in range(302,345):v.update(self.face(),i*.1,100)
        self.assertFalse(v.distance_active)
    def test_fatigue_warmup_blinks_once(self):
        c,v=self.setup_signals()
        for i in range(30):v.update(self.face(ear=.1),i*.1,10)
        self.assertFalse(v.fatigue_fired)
        for i in range(30,50):v.update(self.face(ear=.1 if i%5==0 else .3),i*.1,10800)
        self.assertFalse(v.fatigue_fired)
        for i in range(50,80):v.update(self.face(ear=.1),i*.1,10800)
        self.assertTrue(v.fatigue_fired);v.dismiss('fatigue')
        for i in range(80,120):v.update(self.face(ear=.1),i*.1,10800)
        self.assertEqual(v.generation['fatigue'],1);self.assertIsNone(v.notice(12))
    def test_undo_restores_elapsed_plus_new_time(self):
        c,v=self.setup_signals();c.start();c.timers.timers['water'].elapsed=50
        c.record_drink(True);c.timers.timers['water'].elapsed=12;c.undo_drink()
        self.assertEqual(c.timers.timers['water'].elapsed,62);self.assertEqual(c.drink_count,0)
        with self.assertRaises(ValueError):c.undo_drink()
    def test_preview_actions_do_not_change_timers(self):
        c,v=self.setup_signals();c.preview_notice=('water','preview');c.notice_action('dismiss','water')
        self.assertIsNone(c.preview_notice);self.assertFalse(c.timers.timers['water'].dismissed)
    def test_quiet_suppresses_all_real_notices(self):
        c,v=self.setup_signals();c.start();c.timers.present=True;c.timers.timers['water'].elapsed=4000
        self.assertIsNotNone(c.notice());c.quiet=True;self.assertIsNone(c.notice())

if __name__=='__main__':unittest.main()
