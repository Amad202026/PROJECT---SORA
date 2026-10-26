import unittest
from unittest.mock import patch
import numpy as np
from drink_cycle import DrinkCycle
from drink_vision import DrinkEvidence
from hydration import HydrationMonitor
from hydration_ui import ReminderCenter
from vessel_views import map_box, VesselViews
from vessel_follower import VesselFollower
import test_drinking_fix as fixtures


def evidence(kind='NONE', distance=.4, identity=1, source='face landmarks',valid=True):
    return DrinkEvidence(valid=valid,kind=kind,distance=distance,track_id=identity,
                         mouth_source=source,reason='No reliable vessel',label='cup')


class CycleTests(unittest.TestCase):
    def setUp(self): self.cycle=DrinkCycle();self.now=0;self.events=[]
    def feed(self,item,count):
        for _ in range(count):
            result=self.cycle.update(item,self.now)
            self.now=round(self.now+.1,5)
            if result:self.events.append(result)
    def approach_contact(self,kind='REGISTERED'):
        self.feed(evidence(),8)
        self.feed(evidence(kind,.03),20)
    def test_automatic_after_full_cycle_not_while_holding(self):
        for kind in ['DIRECT','REGISTERED','UNCERTAIN']:
            self.setUp();self.approach_contact(kind)
            self.assertEqual(self.events,[])
            self.feed(evidence(),8)
            self.assertEqual(self.events,['AUTO_SIP'])
    def test_no_initial_approach_no_count(self):
        self.feed(evidence('DIRECT',.03),40);self.feed(evidence(),10)
        self.assertFalse(self.events)
    def test_short_contact_does_not_count(self):
        self.feed(evidence(),8);self.feed(evidence('DIRECT',.03),5);self.feed(evidence(),8)
        self.assertFalse(self.events)
    def test_stationary_near_face_does_not_count(self):
        self.approach_contact();self.feed(evidence('REGISTERED',.03),80)
        self.assertFalse(self.events)
    def test_disappearing_is_not_retreat(self):
        self.approach_contact();self.feed(evidence(valid=False),20)
        self.assertFalse(self.events)
    def test_identity_change_cannot_complete_cycle(self):
        self.approach_contact();self.feed(evidence(identity=2),10)
        self.assertFalse(self.events)
    def test_hidden_mouth_only_never_counts(self):
        self.feed(evidence(),8);self.feed(evidence('OCCLUDED',.03,source='recent mouth reference'),20)
        self.feed(evidence(),10);self.assertFalse(self.events)
    def test_straw_never_auto_counts(self):
        self.approach_contact('STRAW');self.feed(evidence(),10)
        self.assertFalse(self.events)
    def test_cooldown_survives_tracking_loss(self):
        self.approach_contact();self.feed(evidence(),8)
        self.feed(evidence(valid=False),10)
        self.feed(evidence(identity=2),8);self.feed(evidence('DIRECT',.03,identity=2),20)
        self.feed(evidence(identity=2),8)
        self.assertEqual(self.events,['AUTO_SIP'])
    def test_short_gap_does_not_contribute_contact_time(self):
        self.feed(evidence(),8);self.feed(evidence('DIRECT',.03),5)
        self.feed(evidence(valid=False),3);self.feed(evidence('DIRECT',.03),5)
        self.feed(evidence(),8);self.assertFalse(self.events)
    def test_long_frame_gap_cancels_candidate(self):
        self.approach_contact();self.now+=2;self.feed(evidence(),8)
        self.assertFalse(self.events)
    def test_second_cycle_can_count_after_cooldown(self):
        self.approach_contact();self.feed(evidence(),8)
        self.feed(evidence(),110);self.feed(evidence('DIRECT',.03),20);self.feed(evidence(),8)
        self.assertEqual(self.events,['AUTO_SIP','AUTO_SIP'])


class QuietIntegrationTests(unittest.TestCase):
    def test_uncertain_input_never_creates_pending_popup(self):
        class Vision:
            def __init__(self,*args):pass
            def observe(self,*args):return evidence('UNCERTAIN',.03)
            def clear(self):pass
            def track_registered(self,*args):pass
        with patch('hydration.DrinkVision',Vision):m=HydrationMonitor('.',fixtures.Log())
        for n in range(500):m.update(None,None,True,False,n*.1)
        self.assertIsNone(m.pending);self.assertEqual(m.clock.count,0)
    def test_ui_ignores_even_legacy_pending_candidate(self):
        ui=ReminderCenter.__new__(ReminderCenter)
        ui.set_hydration(False,{'id':2})
        self.assertIsNone(ui.pending)
    def test_water_dismissal_survives_presence_flicker(self):
        ui=ReminderCenter.__new__(ReminderCenter)
        ui.water_dismissed=True
        ui.set_hydration(False,None)
        ui.set_hydration(True,None)
        self.assertTrue(ui.water_dismissed)
    def test_completed_cycle_records_without_question(self):
        class Vision:
            item=evidence()
            def __init__(self,*args):pass
            def observe(self,*args):return self.item
            def clear(self):pass
            def track_registered(self,*args):pass
        with patch('hydration.DrinkVision',Vision):m=HydrationMonitor('.',fixtures.Log())
        t=0
        for item,count in [(evidence(),5),(evidence('REGISTERED',.03),10),(evidence(),5)]:
            m.vision.item=item
            for _ in range(count):m.update(None,None,True,False,t);t+=.25
        self.assertEqual(m.clock.count,1);self.assertIsNone(m.pending)


class ViewTests(unittest.TestCase):
    def test_inverse_mirror_coordinates(self):
        result=map_box([10,20,50,60],np.array([[-1,0,639],[0,1,0]]),640,480)
        np.testing.assert_allclose(result,[589,20,629,60])
    def test_multiview_nms_deduplicates_same_box(self):
        class Detector:
            count=0
            def detect(self,frame):
                self.count+=1
                return [dict(box=np.array([100,50,200,150] if self.count==1 else [439,50,539,150],float),label='cup',score=.8)]
        view=VesselViews(Detector())
        ds=view.detect(np.zeros((480,640,3),np.uint8))
        self.assertEqual(len(ds),1)
        np.testing.assert_allclose(ds[0]['box'],[100,50,200,150])


class FollowerTests(unittest.TestCase):
    def test_model_seeds_tracker_identity_persists_and_expires(self):
        follower=VesselFollower();frame=fixtures.RegistrationTests().pattern()
        item=dict(box=np.array([90,60,190,170],float),label='cup',score=.8)
        first=follower.reconcile([item],frame,0)
        self.assertIsNotNone(first)
        identity=first['identity']
        follower.update(frame,.2)
        self.assertEqual(follower.reconcile([],frame,.2)['identity'],identity)
        for i in range(1,44):follower.update(frame,.2+i*.2)
        self.assertIsNone(follower.current)
    def test_no_person_does_not_seed_tracker(self):
        follower=VesselFollower();frame=fixtures.RegistrationTests().pattern()
        item=dict(box=np.array([90,60,190,170],float),label='cup',score=.8)
        self.assertIsNone(follower.reconcile([item],frame,0,allow_start=False))


if __name__=='__main__':unittest.main()
