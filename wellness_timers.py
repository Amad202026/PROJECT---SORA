"""Session reminders from time and observed presence, never a health diagnosis."""
from dataclasses import dataclass
from copy import deepcopy


def duration(seconds):
    seconds=max(0,int(seconds));minutes,seconds=divmod(seconds,60);hours,minutes=divmod(minutes,60)
    return f'{hours:02}:{minutes:02}:{seconds:02}'


@dataclass
class Timer:
    enabled: bool
    interval: float
    elapsed: float = 0.0
    dismissed: bool = False
    snooze_until: float = 0.0
    generation: int = 0
    announced: bool = False


class WellnessTimers:
    def __init__(self, config, logger):
        self.config=deepcopy(config);self.logger=logger
        self.timers={key:Timer(config[key]['enabled'],config[key]['interval_seconds']) for key in ('water','movement','eyes','sleep')}
        self.enabled={key:config[key]['enabled'] for key in ('posture','dark_camera')}
        self.now=0.0;self.previous_time=None;self.previous_running=False;self.previous_active=False
        self.present=False;self.paused=False;self.calibrating=False
        self.observed=0.0;self.break_elapsed=0.0;self.in_break=False;self.break_announced=False
        self.break_generation=0;self.posture_reset_requested=False
        self.dark=False;self.dark_elapsed=0.0;self.light_elapsed=0.0;self.dark_dismissed=False;self.dark_generation=0
        self.posture_active=False;self.posture_dismissed=False;self.posture_snooze=0.0;self.posture_generation=0
        self.request_exit=False
        self.dark_snooze=0.;self.break_snooze=0.

    def update(self, now, present, paused=False, calibrating=False, brightness=255):
        dt=0.0 if self.previous_time is None else max(0.0,now-self.previous_time)
        if dt>2.0:
            self.logger.write('processing_gap_excluded',seconds=round(dt,2));dt=0.0
        self.previous_time=self.now=now
        self.present,self.paused,self.calibrating=present,paused,calibrating
        threshold=self.config['dark_camera']['brightness_threshold']
        if brightness<threshold:
            self.dark_elapsed+=dt;self.light_elapsed=0.0
            if not self.dark and self.dark_elapsed>=self.config['dark_camera']['hold_seconds']:
                self.dark=True;self.dark_dismissed=False;self.dark_generation+=1
                self.logger.write('camera_low_light',mean_brightness=round(brightness,1))
        elif brightness>=threshold+10:
            self.dark_elapsed=0.0;self.light_elapsed+=dt
            if self.dark and self.light_elapsed>=3:
                self.dark=False;self.dark_dismissed=False
                self.logger.write('camera_light_restored')
        else:
            self.dark_elapsed=self.light_elapsed=0.0
        running=not paused and not calibrating
        active=running and present and brightness>=threshold and not self.dark and not self.in_break
        if running and self.previous_running:
            if self.timers['water'].enabled:self.timers['water'].elapsed+=dt
            if self.in_break:
                self.break_elapsed+=dt
                if self.break_complete and not self.break_announced:
                    self.break_announced=True;self.logger.write('break_timer_finished',verified_rest=False)
        if active and self.previous_active:
            self.observed+=dt
            for name in ('movement','eyes','sleep'):
                if self.timers[name].enabled:self.timers[name].elapsed+=dt
        self.previous_running,self.previous_active=running,active
        for name,timer in self.timers.items():
            if timer.enabled and timer.elapsed>=timer.interval and not timer.announced:
                timer.announced=True
                self.logger.write('timer_due',kind=name,elapsed_seconds=round(timer.elapsed,1))

    @property
    def break_complete(self):return self.in_break and self.break_elapsed>=self.config['break_seconds']

    def set_posture(self, active):
        active=active and self.enabled['posture']
        if active and not self.posture_active:self.posture_generation+=1
        if not active:self.posture_dismissed=False;self.posture_snooze=0.0
        self.posture_active=active

    def notice(self):
        if self.paused or self.calibrating:return None
        if self.in_break:return ('break_done',self.break_generation) if self.break_complete and self.now>=self.break_snooze else None
        if self.enabled['dark_camera'] and self.dark and not self.dark_dismissed and self.now>=self.dark_snooze:return ('dark_camera',self.dark_generation)
        if not self.present or self.dark:return None
        for name in ('sleep','eyes','movement','water'):
            timer=self.timers[name]
            if timer.enabled and timer.elapsed>=timer.interval and not timer.dismissed and self.now>=timer.snooze_until:
                return (name,timer.generation)
        if self.posture_active and not self.posture_dismissed and self.now>=self.posture_snooze:
            return ('posture',self.posture_generation)
        return None

    def dismiss(self, kind):
        if kind in self.timers:self.timers[kind].dismissed=True
        elif kind=='posture':self.posture_dismissed=True
        elif kind=='dark_camera':self.dark_dismissed=True
        elif kind=='break_done':self.resume_break()
        self.logger.write('notice_dismissed',kind=kind,timer_reset=False)

    def snooze(self, kind):
        until=self.now+self.config['snooze_seconds']
        if kind in self.timers:self.timers[kind].snooze_until=until
        elif kind=='posture':self.posture_snooze=until
        elif kind=='dark_camera':self.dark_snooze=until
        elif kind=='break_done':self.break_snooze=until
        self.logger.write('notice_snoozed',kind=kind,seconds=self.config['snooze_seconds'])

    def reset_timer(self, kind, source):
        timer=self.timers[kind]
        timer.elapsed=0.0;timer.dismissed=False;timer.snooze_until=0.0;timer.announced=False;timer.generation+=1
        self.logger.write('timer_reset',kind=kind,source=source)

    def start_break(self):
        if self.in_break:return
        self.in_break=True;self.break_elapsed=0.0;self.break_announced=False;self.break_generation+=1
        self.break_snooze=0.
        self.previous_active=False;self.posture_reset_requested=True
        self.logger.write('break_started',planned_seconds=self.config['break_seconds'])

    def resume_break(self):
        if not self.in_break:return
        complete=self.break_complete
        if complete:
            for kind in ('eyes','movement'):self.reset_timer(kind,'completed_user_started_break_timer')
        self.in_break=False;self.previous_active=False;self.posture_reset_requested=True
        self.logger.write('break_resumed',completed_timer=complete,verified_rest=False)

    def toggle(self, kind):
        if kind in self.timers:
            self.timers[kind].enabled=not self.timers[kind].enabled
            self.reset_timer(kind,'feature_toggled')
            value=self.timers[kind].enabled
        else:
            self.enabled[kind]=not self.enabled[kind];value=self.enabled[kind]
            if kind=='posture':self.posture_reset_requested=True;self.set_posture(False)
        self.logger.write('feature_toggled',kind=kind,enabled=value)

    def handle_key(self,key):
        if key in (ord('w'),ord('W')):self.reset_timer('water','user_reported_drink')
        elif key in (ord('m'),ord('M')):self.reset_timer('movement','user_reported_movement')
        elif key in (ord('b'),ord('B')):
            self.resume_break() if self.in_break else self.start_break()
        elif ord('1')<=key<=ord('6'):
            self.toggle(('water','movement','eyes','sleep','posture','dark_camera')[key-ord('1')])

    def lines(self):
        observation='counting' if self.previous_active else 'paused / not reliably observed'
        result=[f'Observed session: {duration(self.observed)} | {observation}']
        for name,timer in self.timers.items():
            state='OFF' if not timer.enabled else ('dismissed - awaiting action' if timer.dismissed else f'snoozed {duration(timer.snooze_until-self.now)}' if self.now<timer.snooze_until else 'DUE' if timer.elapsed>=timer.interval else f'in {duration(timer.interval-timer.elapsed)}')
            result.append(f'{name.capitalize()}: {state}')
        result.append('Break: '+('finished - B to resume' if self.break_complete else duration(self.config['break_seconds']-self.break_elapsed) if self.in_break else 'B to start'))
        result.append('W: drank   M: moved   B: break/resume | 1 water 2 move 3 eyes')
        result.append(f"4 session limit | 5 posture {'ON' if self.enabled['posture'] else 'OFF'} | 6 camera notice {'ON' if self.enabled['dark_camera'] else 'OFF'}")
        return result
