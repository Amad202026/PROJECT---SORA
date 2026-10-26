"""Serialized UI commands and camera observations; no UI or model dependencies."""
from copy import deepcopy
from datetime import datetime
from pathlib import Path
import json
import time
import uuid

from wellness_timers import WellnessTimers
from timer_settings import load_settings
from visual_signals import VisualSignals
from companion_agent import CompanionAgent
from observation_extras import ObservationExtras


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf-8')
    temporary.replace(path)


class SessionController:
    def __init__(self, root, config, demo=False, persist=True):
        self.root=Path(root); self.config=deepcopy(config); self.demo=demo; self.persist=persist
        self.phase='idle'; self.camera='Camera off'; self.posture='UNKNOWN'
        self.calibrated=False; self.calibrating=False; self.calibration_message='Calibration required'
        self.calibration_progress=0; self.error=''; self.fps=0; self.last_calibration=None
        self.preferences={'sound':False,'position':'center','animation':True,'autostart':False}
        self.preview_notice=None;self.quiet=False
        pref=self.root/'ui_preferences.json'
        if persist and pref.exists():
            try:
                p=json.loads(pref.read_text()); self.preferences={'sound':p.get('sound') is True,'position':'edge' if p.get('position')=='edge' else 'center','animation':p.get('animation',True) is True,'autostart':p.get('autostart') is True}
            except (ValueError,OSError):pass
        self.reset_session()

    def reset_session(self):
        self.session_id=None; self.started_at=None; self.active_seconds=0.; self.known_seconds=0.; self.near_seconds=0.
        self.streak=0.; self.longest_streak=0.; self.completed_breaks=0; self.events=[]; self.hourly={};self.daily={}
        self.previous_time=None; self.previous_valid=False; self.previous_near=False
        self.timers=WellnessTimers(self.config,self)
        reference=self.signals.reference if hasattr(self,'signals') else None
        self.signals=VisualSignals(self.config,self);self.signals.reference=reference
        self.drinking_status='Waiting for a session';self.drink_count=0;self.last_auto=None
        self.last_drink_source=None
        self.vision_reset_requested=True;self.vision_error=''
        self.meeting_active=False;self.meeting_status='Automatic meeting detection off';self.ignore_meeting=False
        self.agent=CompanionAgent(self.root,self,self.demo,self.persist)
        self.extras=ObservationExtras(self)

    def write(self,event,**details):
        self.events.append({'time':datetime.now().astimezone().isoformat(),'event':event,'details':details})
        if len(self.events)>500:self.events=self.events[-500:]
        if event=='break_resumed' and details.get('completed_timer'):
            self.completed_breaks+=1;self.day_metrics()['completed_breaks']+=1

    def day_metrics(self):
        day=datetime.now().astimezone().date().isoformat()
        return self.daily.setdefault(day,{'known_seconds':0.,'near_seconds':0.,'completed_breaks':0})

    def start(self):
        if self.phase not in ('idle','ended'):raise ValueError('A session is already open. End it before starting another.')
        self.reset_session(); self.session_id=uuid.uuid4().hex;self.started_at=datetime.now().astimezone().isoformat()
        self.phase='running';self.error='';self.reset_boundary();self.write('session_started',demo=self.demo)

    def reset_boundary(self):
        self.previous_time=None;self.previous_valid=False;self.previous_near=False;self.streak=0
        self.timers.previous_time=None;self.timers.previous_active=False;self.timers.previous_running=False
        self.timers.set_posture(False);self.timers.posture_reset_requested=True
        self.signals.interrupt();self.vision_reset_requested=True
        self.extras.reset_boundary()

    def pause(self):
        if self.phase!='running':raise ValueError('There is no running session to pause.')
        self.phase='paused';self.camera='Camera off — session paused';self.posture='UNKNOWN';self.reset_boundary()
        self.timers.paused=True;self.write('session_paused')

    def resume(self):
        if self.phase!='paused':raise ValueError('There is no paused session to resume.')
        self.phase='running';self.reset_boundary();self.error='';self.write('session_resumed')

    def observe(self,now,present,state,brightness=255,calibrating=False):
        self.posture=state; self.calibrating=calibrating
        running=self.phase=='running' and not calibrating
        dt=0 if self.previous_time is None else max(0,now-self.previous_time)
        if dt>2:dt=0
        valid=running and not self.timers.in_break and brightness>=self.config['dark_camera']['brightness_threshold'] and state in ('NEAR_REFERENCE','LOWER_HEAD_POSITION')
        near=valid and state=='NEAR_REFERENCE'
        previous_observed=self.timers.observed
        self.timers.update(now,present,not running,calibrating,brightness)
        self.active_seconds=self.timers.observed
        hour=datetime.now().astimezone().strftime('%Y-%m-%dT%H')
        self.hourly[hour]=self.hourly.get(hour,0)+self.timers.observed-previous_observed
        if valid and self.previous_valid:
            self.known_seconds+=dt
            self.day_metrics()['known_seconds']+=dt
            if near and self.previous_near:
                self.near_seconds+=dt;self.streak+=dt;self.day_metrics()['near_seconds']+=dt
            else:self.streak=0
        else:self.streak=0
        self.longest_streak=max(self.longest_streak,self.streak)
        self.previous_time=now;self.previous_valid=valid;self.previous_near=near

    def summary(self):
        return dict(id=self.session_id,started_at=self.started_at,updated_at=datetime.now().astimezone().isoformat(),
                    phase=self.phase,active_seconds=self.active_seconds,known_seconds=self.known_seconds,
                    near_seconds=self.near_seconds,longest_streak=self.longest_streak,completed_breaks=self.completed_breaks,
                    events=self.events,hourly=self.hourly,daily=self.daily,demo=self.demo)

    def checkpoint(self):
        if self.session_id and self.persist:atomic_json(self.root/'sessions'/f'{self.session_id}.json',self.summary())

    def end(self):
        if self.phase in ('running','paused'):
            self.phase='ended';self.write('session_ended');self.checkpoint()
        self.camera='Camera off';self.posture='UNKNOWN';self.calibrating=False;self.reset_boundary();self.timers.paused=True

    def save_settings(self,raw,preferences):
        if self.phase in ('running','paused'):raise ValueError('End the current session before saving reminder settings.')
        # Reuse the core validator without writing an unvalidated file.
        class ValuePath:
            def exists(self):return True
            def read_text(self,**kwargs):return json.dumps(raw,allow_nan=False)
        config=load_settings(ValuePath())
        if type(preferences.get('sound')) is not bool or preferences.get('position') not in ('center','edge'):
            raise ValueError('Invalid notification preferences.')
        preferences=dict(preferences)
        preferences.setdefault('animation',True)
        preferences.setdefault('autostart',False)
        if type(preferences['animation']) is not bool:raise ValueError('Animation must be true or false.')
        if type(preferences['autostart']) is not bool:raise ValueError('Autostart must be true or false.')
        if self.persist:
            if preferences['autostart']!=self.preferences.get('autostart',False):
                from windows_startup import set_startup
                set_startup(preferences['autostart'],self.root)
            atomic_json(self.root/'settings.json',config);atomic_json(self.root/'ui_preferences.json',preferences)
        self.config=config;self.preferences=deepcopy(preferences);self.demo=False
        self.timers=WellnessTimers(config,self)
        reference=self.signals.reference
        self.signals=VisualSignals(config,self);self.signals.reference=reference

    def record_drink(self, automatic=False):
        if self.phase!='running':raise ValueError('Start or resume a session first.')
        if automatic:
            self.last_auto={'timer':deepcopy(self.timers.timers['water']), 'at':self.timers.now}
        else:self.last_auto=None
        self.drink_count+=1
        self.last_drink_source='likely_visual_sip' if automatic else 'user_reported_drink'
        self.timers.reset_timer('water','likely_visual_sip' if automatic else 'user_reported_drink')
        self.write('drink_recorded',automatic=automatic,estimated=automatic,count=self.drink_count)

    def undo_drink(self):
        if not self.last_auto:raise ValueError('There is no automatic drink to undo.')
        current=self.timers.timers['water'];old=self.last_auto['timer']
        old.elapsed+=current.elapsed;old.generation=current.generation+1
        self.timers.timers['water']=old;self.drink_count=max(0,self.drink_count-1);self.last_auto=None
        self.write('automatic_drink_undone')

    def notice(self):
        if self.preview_notice:return self.preview_notice
        return self.agent.step(self.raw_notice(),self)

    def raw_notice(self):
        if self.phase!='running':return None
        timer=self.timers.notice()
        if self.timers.paused or self.timers.calibrating or self.timers.in_break or self.timers.dark or not self.timers.present:return timer
        if timer and timer[0] in ('sleep','dark_camera'):return timer
        return self.signals.notice(self.timers.now) or timer

    def notice_action(self, action, kind):
        if self.preview_notice:
            self.preview_notice=None;return
        self.agent.user_action(action,kind)
        if kind=='agent_break':
            kind=self.agent.current['goal'] if self.agent.current else 'posture'
        if kind in ('distance','fatigue'):
            if action=='snooze':self.signals.snooze(kind,self.timers.now)
            else:self.signals.dismiss(kind)
            self.write('notice_'+action,kind=kind)
        else:getattr(self.timers,action)(kind)

    def history(self):
        today=datetime.now().astimezone().date(); records=[]
        if self.persist:
            for p in (self.root/'sessions').glob('*.json'):
                try:records.append(json.loads(p.read_text(encoding='utf-8')))
                except (ValueError,OSError):continue
        records=[r for r in records if r.get('id')!=self.session_id]
        if self.session_id:records.append(self.summary())
        selected=[]
        for r in records:
            try:
                if datetime.fromisoformat(r['started_at']).astimezone().date()==today:selected.append(r)
            except (ValueError,KeyError,TypeError):continue
        day_stats=[r.get('daily',{}).get(str(today),{}) for r in records]
        known=sum(r.get('known_seconds',0) for r in day_stats);near=sum(r.get('near_seconds',0) for r in day_stats)
        hours=[0.]*24
        for r in records:
            for h,v in r.get('hourly',{}).items():
                if h[:10]==str(today):hours[int(h[-2:])]+=v
        events=sorted([e for r in records for e in r.get('events',[]) if e['time'][:10]==str(today)],key=lambda e:e['time'],reverse=True)
        return dict(active_seconds=sum(hours),near_percent=round(100*near/known) if known else None,
                    completed_breaks=sum(r.get('completed_breaks',0) for r in day_stats),hours=hours,events=events[:200])

    def snapshot(self):
        notice=self.notice()
        return dict(phase=self.phase,camera=self.camera,posture=self.posture,calibrated=self.calibrated,
                    calibrating=self.calibrating,calibration_message=self.calibration_message,
                    calibration_progress=self.calibration_progress,last_calibration=self.last_calibration,
                    active_seconds=self.active_seconds,near_percent=round(100*self.near_seconds/self.known_seconds) if self.known_seconds else None,
                    known_seconds=self.known_seconds,longest_streak=self.longest_streak,error=self.error,fps=round(self.fps,1),
                    demo=self.demo,config=self.config,preferences=self.preferences,notice=notice,
                    distance=self.signals.distance,fatigue=self.signals.fatigue,vision_error=self.vision_error,
                    drinking_status=self.drinking_status,drink_count=self.drink_count,can_undo_drink=self.last_auto is not None,quiet=self.quiet,
                    agent=self.agent.snapshot(),meeting=self.meeting_status,meeting_active=self.meeting_active,ignore_meeting=self.ignore_meeting,
                    orientation=self.extras.orientation,possible_yawns=len(self.extras.yawns),
                    in_break=self.timers.in_break,break_remaining=max(0,self.config['break_seconds']-self.timers.break_elapsed),
                    timers={k:dict(enabled=t.enabled,remaining=max(0,t.interval-t.elapsed)) for k,t in self.timers.timers.items()})
