"""Local Figma UI + existing OpenCV engine. No cloud or front-end build required."""
from pathlib import Path
from datetime import datetime
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from urllib.parse import urlsplit
from queue import Queue,Empty
from threading import Thread,Event,RLock
import argparse,json,mimetypes,secrets,time,webbrowser
from session_controller import SessionController
from timer_settings import load_settings

ROOT=Path(__file__).resolve().parent

class Application:
    def __init__(self,root=ROOT,demo=False,no_camera=False):
        self.root=Path(root);self.lock=RLock();self.commands=Queue();self.stop=Event();self.jpeg=None;self.debug_preview=False
        self.controller=SessionController(root,load_settings(self.root/'settings.json',demo),demo)
        self.no_camera=no_camera;self.worker=Thread(target=self.run,daemon=True)

    def submit(self,action,data=None):
        result={};done=Event();self.commands.put((action,data or {},result,done))
        if not done.wait(15):raise ValueError('The camera is taking too long to respond. Please wait, then check the session status.')
        if 'error' in result:raise ValueError(result['error'])
        return result

    def run(self):
        import cv2
        from vendor.mp_persondet import MPPersonDet
        from vendor.mp_pose import MPPose
        from pose_tracking import infer_landmarks
        from pose_test import get_visible_points
        from calibration import PostureCalibration
        from posture_state import PostureState
        from posture_reminder import PostureReminder
        from camera_overlay import draw_tracking_overlay
        from face_vision import FaceVision
        from drinking_auto import DrinkingAuto
        from meeting_detector import MeetingDetector, MeetingProbe
        meeting=MeetingDetector();meeting_probe=MeetingProbe();meeting_at=-999
        c=self.controller;camera=None;detector=estimator=None
        face_engine=drink_engine=None;vision_attempted=False
        calibration=PostureCalibration(self.root/'posture_reference.json');posture=PostureState()
        reminder=PostureReminder(window_seconds=c.config['posture']['window_seconds'])
        preview_requested=False;last_save=time.monotonic();previous_state=None
        try:
            while not self.stop.is_set():
                try:
                    action,data,result,done=self.commands.get_nowait()
                except Empty:action=None
                if action:
                    try:
                        with self.lock:
                            if action in ('dismiss','snooze','acknowledge') and data.get('kind')=='agent_break':
                                goal=c.agent.current
                                if not goal or goal['stage']!=2 or data.get('notice_id')!=f"{goal['goal']}:{goal['generation']}":
                                    raise ValueError('This reminder has changed. Use the current reminder.')
                            if action=='start':c.start()
                            elif action=='pause':self.debug_preview=False;c.pause();calibration.active=False;preview_requested=False;c.calibrating=False
                            elif action=='resume':c.resume()
                            elif action=='end':self.debug_preview=False;c.end();calibration.active=False;preview_requested=False
                            elif action=='calibrate':
                                if c.phase=='paused':raise ValueError('Resume the session before calibration.')
                                c.error=''
                                preview_requested=True;calibration.baseline=None;c.calibrated=False;calibration.start();c.reset_boundary();c.signals.begin_calibration()
                                c.calibrating=True
                            elif action=='open_debug_preview':
                                if c.phase=='paused':raise ValueError('Resume or end the paused session before opening the camera.')
                                self.debug_preview=True;c.error=''
                                if camera is None:c.camera='Starting camera preview...'
                            elif action=='close_debug_preview':
                                self.debug_preview=False
                                if c.phase!='running' and not preview_requested:
                                    c.camera='Camera off';self.jpeg=None
                            elif action=='close_preview':
                                preview_requested=False;calibration.active=False;c.calibrating=False
                            elif action=='save_settings':
                                c.save_settings(data['config'],data['preferences'])
                                reminder=PostureReminder(window_seconds=c.config['posture']['window_seconds'])
                            elif action=='drink':
                                c.record_drink()
                                if drink_engine:drink_engine.reset();drink_engine.cycle.cooldown_until=time.perf_counter()+10
                            elif action=='undo_drink':c.undo_drink()
                            elif action=='move':c.timers.reset_timer('movement','user_reported_movement')
                            elif action=='break':c.timers.start_break();c.reset_boundary()
                            elif action=='resume_break':c.timers.resume_break();c.reset_boundary()
                            elif action in ('dismiss','snooze'):c.notice_action(action,data['kind'])
                            elif action=='ignore_meeting':c.ignore_meeting=not c.ignore_meeting;c.meeting_active=False;c.write('meeting_override',enabled=c.ignore_meeting)
                            elif action=='quiet':c.quiet=not c.quiet;c.write('quiet_mode',enabled=c.quiet)
                            elif action=='preview_notice':
                                if data.get('kind') not in ('water','movement','eyes','sleep','posture','distance','fatigue'):raise ValueError('Unknown preview')
                                c.preview_notice=(data['kind'],'preview')
                            elif action=='acknowledge':
                                kind=data['kind']
                                if c.preview_notice:c.preview_notice=None
                                elif kind=='water':
                                    c.record_drink()
                                    if drink_engine:drink_engine.reset();drink_engine.cycle.cooldown_until=time.perf_counter()+10
                                elif kind=='movement':c.timers.reset_timer('movement','user_reported_movement')
                                elif kind=='sleep':self.debug_preview=False;c.end();calibration.active=False;preview_requested=False
                                elif kind in ('eyes','fatigue','agent_break'):
                                    c.notice_action('dismiss',kind);c.timers.start_break();c.reset_boundary()
                                elif kind=='break_done':c.timers.resume_break();c.reset_boundary()
                                else:c.notice_action('dismiss',kind)
                            elif action=='shutdown':c.end();self.stop.set()
                            else:raise ValueError('Unknown action')
                            result['ok']=True
                    except Exception as exc:result['error']=str(exc)
                    finally:done.set()
                meeting_enabled=c.config.get('automatic_meeting',{}).get('enabled',False) and c.phase=='running' and not c.ignore_meeting
                if time.monotonic()-meeting_at>=5:
                    meeting_at=time.monotonic()
                    sample=meeting_probe.poll(meeting_at,meeting_enabled)
                    with self.lock:
                        before=c.meeting_active;c.meeting_active=meeting.update(sample,meeting_at,meeting_enabled);c.meeting_status=meeting.status
                        if before!=c.meeting_active:c.write('meeting_suppression',active=c.meeting_active,heuristic=True)
                wanted=(c.phase=='running' or preview_requested or self.debug_preview) and not self.no_camera
                if not wanted:
                    if camera is not None:camera.release();camera=None
                    with self.lock:self.jpeg=None
                    self.stop.wait(.03);continue
                try:
                    if detector is None:
                        with self.lock:c.camera='Loading OpenCV models…'
                        if cv2.__version__.split('.')[0]!='5':raise RuntimeError('OpenCV 5 is required. Install requirements.txt.')
                        detector=MPPersonDet(modelPath=str(self.root/'models/person_detection_mediapipe_2023mar.onnx'),scoreThreshold=.5,nmsThreshold=.3)
                        estimator=MPPose(modelPath=str(self.root/'models/pose_estimation_mediapipe_2023mar.onnx'),confThreshold=.8)
                    if camera is None:
                        camera=cv2.VideoCapture(0,cv2.CAP_DSHOW);camera.set(cv2.CAP_PROP_FRAME_WIDTH,640);camera.set(cv2.CAP_PROP_FRAME_HEIGHT,480)
                        if not camera.isOpened():raise RuntimeError('Unable to open camera. Close other camera apps and press Resume or Calibrate to retry.')
                        with self.lock:c.reset_boundary()
                    began=time.perf_counter();ok,frame=camera.read()
                    if not ok or frame is None:raise RuntimeError('Camera frame unavailable. Close other camera apps and press Resume or Calibrate to retry.')
                    if not vision_attempted:
                        vision_attempted=True
                        try:face_engine=FaceVision(self.root/'models/face_landmarker.task')
                        except Exception as exc:
                            with self.lock:c.vision_error='Face indicators unavailable: '+str(exc)
                        try:drink_engine=DrinkingAuto(self.root)
                        except Exception as exc:
                            with self.lock:c.vision_error+=' Drinking unavailable: '+str(exc)
                        # Model initialization does not consume the calibration hold period.
                        if calibration.active:calibration.start()
                    height,width=frame.shape[:2];brightness=float(cv2.mean(cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY))[0])
                    persons=detector.infer(frame) if brightness>=c.config['dark_camera']['brightness_threshold'] else []
                    points={}
                    if len(persons)==1:
                        lm,_=infer_landmarks(frame,persons,detector,estimator)
                        if lm is not None:points=get_visible_points(lm,width,height)
                    now=time.perf_counter()
                    face=None;auto_sip=False
                    with self.lock:
                        if c.vision_reset_requested:
                            if drink_engine:drink_engine.reset()
                            c.vision_reset_requested=False
                    bright=brightness>=c.config['dark_camera']['brightness_threshold']
                    try:
                        if face_engine and bright and len(persons)<=1:face=face_engine.infer(frame,now)
                        if drink_engine:
                            drink_engine.straw_enabled=c.config['straw_assist']['enabled']
                            auto_sip=drink_engine.update(frame,face,now,allowed=(c.phase=='running' and not calibration.active and not c.timers.in_break and bright and len(persons)<=1 and c.config['automatic_drinking']['enabled'] and c.config['water']['enabled']))
                        if face_engine and drink_engine:
                            with self.lock:c.vision_error=''
                    except Exception as exc:
                        if drink_engine:drink_engine.reset()
                        with self.lock:c.vision_error='Visual analysis paused for this frame: '+str(exc)
                    with self.lock:
                        was_calibrating=calibration.active
                        features=calibration.update(points,width,height)
                        if was_calibrating:
                            # Match face reference to the current stable posture segment.
                            if len(calibration.samples)<=1:c.signals.samples=[]
                            c.signals.sample(face)
                        if was_calibrating and not calibration.active and calibration.baseline is not None:
                            c.signals.finish_calibration()
                            c.last_calibration=datetime.now().astimezone().isoformat();c.write('calibration_saved')
                        c.calibrated=calibration.baseline is not None;c.calibration_message=calibration.message
                        c.calibration_progress=min(1,(time.perf_counter()-calibration.stable_since)/calibration.duration) if calibration.active and calibration.stable_since else (1 if c.calibrated else 0)
                        if c.timers.posture_reset_requested:posture.reset();reminder.reset();c.timers.posture_reset_requested=False
                        state='CALIBRATING' if calibration.active else posture.update(features,calibration.baseline)
                        c.observe(time.perf_counter(),len(persons)==1,state,brightness,calibration.active)
                        c.signals.update(face,now,c.active_seconds,usable=c.phase=='running' and not calibration.active and not c.timers.in_break and bright,
                                         drinking=bool(drink_engine and drink_engine.cycle.phase=='CONTACT'))
                        c.drinking_status=drink_engine.label if drink_engine and c.config['automatic_drinking']['enabled'] else 'Automatic drinking off'
                        if auto_sip:c.record_drink(automatic=True)
                        c.extras.update(face,now,len(persons),bright,c.phase=='running' and not calibration.active,
                                        drinking=bool(drink_engine and drink_engine.cycle.phase=='CONTACT'))
                        if (c.config['fatigue']['enabled'] and c.active_seconds>=c.config['fatigue']['warmup_seconds']
                            and len(c.extras.yawns)>=2 and not c.signals.fatigue_fired):
                            c.signals.fatigue_active=c.signals.fatigue_fired=True;c.signals.generation['fatigue']+=1
                            c.write('repeated_yawn_cue',diagnosis=False)
                        c.camera='Camera active - preview only' if c.phase!='running' and not calibration.active else 'Camera too dark' if brightness<c.config['dark_camera']['brightness_threshold'] else 'Multiple people detected' if len(persons)>1 else 'No person detected' if len(persons)==0 else 'Camera active — calibrated' if c.calibrated else 'Camera active — calibration required'
                        if c.phase=='running' and c.calibrated and not calibration.active and not c.timers.in_break and c.timers.enabled['posture']:
                            event=reminder.update(state)
                            if event:c.write('posture_reminder' if event=='REMIND' else 'posture_recovered')
                        else:reminder.reset()
                        c.timers.set_posture(reminder.alert_active)
                        c.notice()  # Drive the agent even when the browser and popup are hidden.
                        if state!=previous_state:c.write('posture_state',state=state);previous_state=state
                        preview=cv2.flip(frame,1)
                        if drink_engine and drink_engine.box is not None:
                            x1,y1,x2,y2=map(int,drink_engine.box)
                            cv2.rectangle(preview,(width-1-x2,y1),(width-1-x1,y2),(255,200,0),2)
                        if face:
                            x,y=map(int,face['mouth']);cv2.circle(preview,(width-1-x,y),4,(255,0,255),-1)
                        draw_tracking_overlay(preview,points,state,c.fps)
                        ok,jpeg=cv2.imencode('.jpg',preview,[cv2.IMWRITE_JPEG_QUALITY,75])
                        if ok:self.jpeg=jpeg.tobytes()
                        c.fps=1/max(.001,time.perf_counter()-began)
                        if time.monotonic()-last_save>10:c.checkpoint();last_save=time.monotonic()
                except Exception as exc:
                    if camera is not None:camera.release();camera=None
                    with self.lock:
                        if c.phase=='running':c.pause()
                        c.error=str(exc);c.camera='Camera unavailable';c.calibrating=False;calibration.active=False;self.jpeg=None
                    preview_requested=False;self.debug_preview=False
        finally:
            if camera is not None:camera.release()
            if face_engine:face_engine.close()
            with self.lock:c.end();self.jpeg=None


def make_server(app):
    token=secrets.token_urlsafe(24);base='/'+token+'/'
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def send(self,status,data,kind='application/json'):
            if not isinstance(data,bytes):data=json.dumps(data,allow_nan=False).encode()
            self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; object-src 'none'; frame-ancestors 'none'")
            self.end_headers()
            try:self.wfile.write(data)
            except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):pass
        def route(self):
            expected=f'127.0.0.1:{self.server.server_port}'
            if self.headers.get('Host')!=expected:return None
            path=urlsplit(self.path).path
            return path[len(base):] if path.startswith(base) else None
        def do_GET(self):
            path=self.route()
            if path is None:return self.send(404,{'error':'Not found'})
            if path=='api/state':
                with app.lock:state=app.controller.snapshot()
                return self.send(200,state)
            if path=='api/history':
                with app.lock:data=app.controller.history()
                return self.send(200,data)
            if path=='api/camera':
                with app.lock:jpeg=app.jpeg
                return self.send(200,jpeg,'image/jpeg') if jpeg else self.send(204,b'')
            target=(app.root/'web'/(path or 'index.html')).resolve();web=(app.root/'web').resolve()
            if not target.is_relative_to(web) or not target.is_file():return self.send(404,{'error':'Not found'})
            return self.send(200,target.read_bytes(),mimetypes.guess_type(str(target))[0] or 'application/octet-stream')
        def do_POST(self):
            if self.route()!='api/action':return self.send(404,{'error':'Not found'})
            origin=f'http://127.0.0.1:{self.server.server_port}'
            if self.headers.get('Origin')!=origin or self.headers.get('Content-Type')!='application/json':return self.send(403,{'error':'Invalid origin'})
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=16384:raise ValueError('Invalid request size')
                data=json.loads(self.rfile.read(size));result=app.submit(data['action'],data.get('data'))
                self.send(200,result)
            except (ValueError,KeyError,TypeError) as exc:self.send(400,{'error':str(exc)})
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    return server,f'http://127.0.0.1:{server.server_port}{base}'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--demo',action='store_true');parser.add_argument('--no-camera',action='store_true');parser.add_argument('--no-browser',action='store_true');parser.add_argument('--no-popup',action='store_true')
    args=parser.parse_args();app=Application(demo=args.demo,no_camera=args.no_camera)
    server,url=make_server(app);Thread(target=server.serve_forever,daemon=True).start();app.worker.start()
    print('Sora UI: '+url,flush=True)
    if not args.no_browser:webbrowser.open(url)
    popup=None
    try:
        if not args.no_popup:
            from animation_popup import DesktopPopup
            popup=DesktopPopup(app)
        while not app.stop.wait(.05):
            if popup:popup.pump()
    except KeyboardInterrupt:app.stop.set()
    finally:
        app.stop.set();app.worker.join(5);server.shutdown();server.server_close()
        if popup:popup.close()

if __name__=='__main__':main()
