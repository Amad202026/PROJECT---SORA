from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from session_controller import SessionController
from timer_settings import DEFAULTS
from agent_policy import decide, handler
from meeting_detector import MeetingDetector
from straw_assist import connects_mouth_to_vessel


class AgentTests(unittest.TestCase):
    def controller(self):
        c=SessionController(Path('.'),deepcopy(DEFAULTS),demo=True,persist=False);c.start()
        c.timers.present=True;c.posture='LOWER_HEAD_POSITION';c.timers.set_posture(True)
        return c
    def test_followup_then_visual_recovery(self):
        c=self.controller();self.assertEqual(c.notice()[0],'posture')
        c.timers.now=9;self.assertEqual(c.notice()[0],'agent_break')
        for t in (10,11,12,13):
            c.timers.now=t;c.posture='NEAR_REFERENCE';c.timers.set_posture(False);self.assertIsNone(c.notice())
        self.assertTrue(any(r['event']=='goal_resolved' for r in c.agent.rows))
        self.assertEqual(sum(r.get('tool')=='offer_break' for r in c.agent.rows),1)
    def test_unknown_is_not_recovery_or_permission_to_repeat(self):
        c=self.controller();c.notice();c.posture='UNKNOWN';c.timers.present=False;c.timers.now=10
        self.assertIsNone(c.notice());self.assertIsNotNone(c.agent.current)
        self.assertFalse(any(r['event']=='goal_resolved' for r in c.agent.rows))
    def test_meeting_defers_and_resumes(self):
        c=self.controller();c.meeting_active=True;self.assertIsNone(c.notice())
        c.meeting_active=False;self.assertEqual(c.notice()[0],'posture')
    def test_dismiss_blocks_followup(self):
        c=self.controller();c.notice();c.notice_action('dismiss','posture');c.timers.now=99
        self.assertIsNone(c.notice());self.assertFalse(any(r.get('tool')=='offer_break' for r in c.agent.rows))
    def test_followup_dismiss_targets_original_goal(self):
        c=self.controller();c.notice();c.timers.now=9;c.notice();c.notice_action('dismiss','agent_break')
        self.assertIsNone(c.notice());self.assertTrue(c.timers.posture_dismissed)
    def test_snooze_respects_duration(self):
        c=self.controller();c.notice();c.notice_action('snooze','posture');c.timers.now=9
        self.assertIsNone(c.notice());c.timers.now=301;self.assertIsNotNone(c.notice())
    def test_one_tool_call_when_ui_polls_repeatedly(self):
        c=self.controller()
        for i in range(50):c.notice()
        self.assertEqual(sum(r.get('tool')=='show_reminder' for r in c.agent.rows),1)
    def test_cloud_contract_rejects_arbitrary_fields(self):
        with self.assertRaises(ValueError):handler({'tool':'shell'},None)
        v={'goal':'water','stage':0,'meeting':False,'quiet':False,'usable':True,'resolved':False,'overdue':False}
        self.assertEqual(handler(v,None),decide(v));v['quiet']=True;self.assertEqual(decide(v)['action'],'defer')
    def test_persistent_trace_survives_event_buffer(self):
        with tempfile.TemporaryDirectory() as tmp:
            c=SessionController(Path(tmp),deepcopy(DEFAULTS),persist=True);c.start();c.timers.present=True
            c.timers.timers['water'].elapsed=4000;c.notice()
            self.assertTrue((Path(tmp)/'sessions'/(c.session_id+'.agent.jsonl')).exists())


class CueTests(unittest.TestCase):
    def test_meeting_debounce_release_and_failure(self):
        m=MeetingDetector();self.assertFalse(m.update(True,0));self.assertFalse(m.update(True,9))
        self.assertTrue(m.update(True,10));self.assertTrue(m.update(False,11));self.assertFalse(m.update(False,56))
        m.active=True;self.assertFalse(m.update(None,57));self.assertIn('unavailable',m.status)
    def test_mic_use_does_not_enable_itself(self):
        m=MeetingDetector();self.assertFalse(m.update(True,100,False))
    def test_yawns_require_sustained_open_close_and_reject_speech(self):
        c=SessionController(Path('.'),deepcopy(DEFAULTS),persist=False);e=c.extras
        def f(opened):return {'frontal':True,'mouth_open_ratio':.9 if opened else .1}
        for i in range(50):e.update(f(i%2==0),i*.1,1,True,True)
        self.assertEqual(len(e.yawns),0)
        for i in range(50,82):e.update(f(True),i*.1,1,True,True)
        e.update(f(False),8.2,1,True,True);self.assertEqual(len(e.yawns),1)
    def test_unknown_face_does_not_complete_yawn(self):
        c=SessionController(Path('.'),deepcopy(DEFAULTS),persist=False);e=c.extras
        for i in range(35):e.update({'frontal':True,'mouth_open_ratio':.9},i*.1,1,True,True)
        e.update(None,3.5,0,True,True);self.assertEqual(len(e.yawns),0)
    def test_straw_geometry_rejects_disconnected_or_internal_edges(self):
        self.assertTrue(connects_mouth_to_vessel((50,50,80,80),(50,50),(75,75,110,140),100))
        self.assertFalse(connects_mouth_to_vessel((80,80,90,130),(50,50),(75,75,110,140),100))
        self.assertFalse(connects_mouth_to_vessel((1,1,30,20),(50,50),(75,75,110,140),100))


if __name__=='__main__':unittest.main()
