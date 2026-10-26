from copy import deepcopy
from pathlib import Path
from threading import Thread
from unittest.mock import patch,Mock
import http.client,json,time,unittest
import numpy as np
from timer_settings import DEFAULTS
from session_controller import SessionController
from sora_ui import Application,make_server

ROOT=Path(__file__).resolve().parent

class Sessions(unittest.TestCase):
    def setUp(self):self.c=SessionController(ROOT,DEFAULTS,persist=False)
    def feed(self,seconds,state='NEAR_REFERENCE',present=True,start=0):
        for n in range(start,start+seconds+1):self.c.observe(float(n),present,state)
    def test_real_stats_and_unknown_gap(self):
        self.c.start();self.feed(10)
        self.assertEqual(self.c.active_seconds,10);self.assertEqual(self.c.snapshot()['near_percent'],100)
        self.c.observe(11,True,'UNKNOWN');self.c.observe(12,True,'LOWER_HEAD_POSITION');self.c.observe(13,True,'LOWER_HEAD_POSITION')
        self.assertEqual(self.c.known_seconds,11);self.assertEqual(self.c.longest_streak,10);self.assertEqual(self.c.streak,0)
        self.assertEqual(self.c.snapshot()['near_percent'],91)
    def test_absence_is_not_near_reference(self):
        self.c.start();self.feed(10,'UNKNOWN',False)
        self.assertIsNone(self.c.snapshot()['near_percent']);self.assertEqual(self.c.active_seconds,0)
        self.assertEqual(self.c.timers.timers['water'].elapsed,10)
    def test_pause_does_not_bridge_time(self):
        self.c.start();self.feed(5);self.c.pause();self.c.resume();self.feed(5,start=100)
        self.assertEqual(self.c.active_seconds,10);self.assertEqual(self.c.longest_streak,5)
    def test_end_is_idempotent_and_new_start_resets(self):
        self.c.start();self.feed(5);self.c.end();self.c.end()
        self.assertEqual(sum(e['event']=='session_ended' for e in self.c.events),1)
        self.assertEqual(self.c.active_seconds,5);self.c.start();self.assertEqual(self.c.active_seconds,0)
        self.assertTrue(self.c.timers.posture_reset_requested)
    def test_large_stall_is_excluded(self):
        self.c.start();self.c.observe(0,True,'NEAR_REFERENCE');self.c.observe(30,True,'NEAR_REFERENCE')
        self.assertEqual(self.c.known_seconds,0);self.assertEqual(self.c.active_seconds,0)
    def test_calibration_excludes_time(self):
        self.c.start()
        for n in range(5):self.c.observe(n,True,'CALIBRATING',calibrating=True)
        self.assertEqual(self.c.active_seconds,0);self.assertEqual(self.c.timers.timers['water'].elapsed,0)
    def test_settings_validation_and_active_guard(self):
        raw=deepcopy(DEFAULTS);raw['water']['interval_seconds']=-1
        with self.assertRaises(ValueError):self.c.save_settings(raw,{'sound':False,'position':'center'})
        self.assertEqual(self.c.config,DEFAULTS)
        self.c.start()
        with self.assertRaises(ValueError):self.c.save_settings(DEFAULTS,{'sound':False,'position':'center'})
    def test_completed_break_counter(self):
        self.c.start();self.c.timers.start_break();self.c.timers.break_elapsed=self.c.config['break_seconds'];self.c.timers.resume_break()
        self.assertEqual(self.c.completed_breaks,1);self.c.timers.resume_break();self.assertEqual(self.c.completed_breaks,1)
    def test_current_session_history(self):
        self.c.start();self.feed(6);h=self.c.history()
        self.assertEqual(h['active_seconds'],6);self.assertEqual(h['near_percent'],100)
    def test_atomic_save_uses_validated_values(self):
        self.c.persist=True
        with patch('session_controller.atomic_json') as save:
            self.c.save_settings(DEFAULTS,{'sound':True,'position':'edge'})
            self.assertEqual(save.call_count,2)
        self.assertEqual(self.c.preferences['position'],'edge')

class Api(unittest.TestCase):
    def setUp(self):
        self.app=Application(ROOT,no_camera=True);self.app.controller.persist=False
        self.server,self.url=make_server(self.app);self.prefix=self.url.split(str(self.server.server_port),1)[1]
        self.thread=Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.app.worker.start()
    def tearDown(self):
        self.app.stop.set();self.app.worker.join(5);self.server.shutdown();self.server.server_close()
    def request(self,path,method='GET',data=None,headers=None):
        con=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=10)
        con.request(method,self.prefix+path,json.dumps(data) if data else None,headers or {})
        r=con.getresponse();status=r.status;body=r.read();con.close();return status,body
    def post(self,action,data=None):
        return self.request('api/action','POST',{'action':action,'data':data or {}},{'Origin':f'http://127.0.0.1:{self.server.server_port}','Content-Type':'application/json'})
    def test_controls_round_trip(self):
        self.assertEqual(self.post('start')[0],200)
        with self.app.lock:
            c=self.app.controller;c.posture='LOWER_HEAD_POSITION';c.timers.present=True;c.timers.set_posture(True)
            c.notice();c.timers.now=121;notice=c.notice();self.assertEqual(notice[0],'agent_break')
        self.assertEqual(self.post('acknowledge',{'kind':'agent_break','notice_id':'stale'})[0],400)
        self.assertEqual(self.post('acknowledge',{'kind':'agent_break','notice_id':notice[1]})[0],200)
        self.assertTrue(self.app.controller.timers.in_break)
        self.assertEqual(self.post('pause')[0],200);self.assertEqual(json.loads(self.request('api/state')[1])['phase'],'paused')
        self.assertEqual(self.post('resume')[0],200);self.assertEqual(self.post('end')[0],200)
        self.assertEqual(json.loads(self.request('api/state')[1])['phase'],'ended')
    def test_errors_return_to_ui(self):
        status,body=self.post('resume');self.assertEqual(status,400);self.assertIn('no paused session',body.decode())
    def test_host_origin_and_traversal_checks(self):
        self.assertEqual(self.request('api/state',headers={'Host':'evil.example'})[0],404)
        self.assertEqual(self.request('api/action','POST',{'action':'start'},{'Content-Type':'application/json'})[0],403)
        self.assertEqual(self.request('../settings.json')[0],404)
    def test_local_assets_served(self):
        self.assertEqual(self.request('')[0],200);self.assertEqual(self.request('assets/Home_imgShield.svg')[0],200)
        self.assertEqual(self.request('api/camera')[0],204)

class CameraWorker(unittest.TestCase):
    def run_app(self,read_ok=True):
        camera=Mock();camera.isOpened.return_value=True
        def read():time.sleep(.015);return (True,np.zeros((480,640,3),np.uint8)) if read_ok else (False,None)
        camera.read.side_effect=read
        app=Application(ROOT);app.controller.persist=False
        return app,camera
    def test_pause_and_end_release_camera(self):
        app,camera=self.run_app()
        with patch('cv2.VideoCapture',return_value=camera),patch('vendor.mp_persondet.MPPersonDet'),patch('vendor.mp_pose.MPPose'),patch('face_vision.FaceVision',return_value=Mock(infer=Mock(return_value=None))),patch('drinking_auto.DrinkingAuto',return_value=Mock(update=Mock(return_value=False),box=None,cycle=Mock(phase='WAIT'),label='Test')):
            app.worker.start()
            try:
                app.submit('start')
                until=time.monotonic()+3
                while camera.read.call_count==0 and time.monotonic()<until:time.sleep(.02)
                app.submit('pause');time.sleep(.05);self.assertTrue(camera.release.called)
                app.submit('resume');app.submit('end');time.sleep(.05)
                self.assertEqual(app.controller.phase,'ended')
            finally:app.stop.set();app.worker.join(3)
    def test_camera_failure_pauses_and_reports(self):
        app,camera=self.run_app(False)
        with patch('cv2.VideoCapture',return_value=camera),patch('vendor.mp_persondet.MPPersonDet'),patch('vendor.mp_pose.MPPose'),patch('face_vision.FaceVision',return_value=Mock(infer=Mock(return_value=None))),patch('drinking_auto.DrinkingAuto',return_value=Mock(update=Mock(return_value=False),box=None,cycle=Mock(phase='WAIT'),label='Test')):
            app.worker.start()
            try:
                app.submit('start');until=time.monotonic()+3
                while not app.controller.error and time.monotonic()<until:time.sleep(.02)
                self.assertEqual(app.controller.phase,'paused');self.assertIn('frame unavailable',app.controller.error)
                self.assertTrue(camera.release.called)
            finally:app.stop.set();app.worker.join(3)

if __name__=='__main__':unittest.main()
