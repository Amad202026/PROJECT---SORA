"""Outcome-aware controller: perceive, select a tool, observe, re-plan once."""
from datetime import datetime, timezone
import json
from pathlib import Path
from agent_policy import decide
from cloud_policy import CloudPolicy


class CompanionAgent:
    def __init__(self, root, logger, demo=False, persist=True):
        self.root=Path(root); self.logger=logger; self.persist=persist
        self.cloud=CloudPolicy(root); self.delay=8 if demo else 120
        self.current=None; self.shown=None; self.rows=[]; self.last_decision=None
        self.recovered_since=None; self.status='Waiting for observations'
        self.goals={};self.completed=set()

    def trace(self, event, **data):
        row={'time':datetime.now(timezone.utc).isoformat(), 'event':event, **data}
        self.rows.append(row); self.rows=self.rows[-200:]
        if self.persist and self.logger.session_id:
            path=self.root/'sessions'/(self.logger.session_id+'.agent.jsonl')
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open('a', encoding='utf-8') as file:file.write(json.dumps(row, allow_nan=False)+'\n')
            except OSError:self.status='Trace storage unavailable'

    def outcome(self, c, now):
        if not self.current:return False
        kind=self.current['goal']
        good=False
        if kind=='posture':good=c.posture=='NEAR_REFERENCE' and c.timers.present and not c.timers.dark
        elif kind=='distance':return c.signals.previous_valid and not c.signals.distance_active and c.signals.distance=='Near reference'
        elif kind in c.timers.timers:
            return c.timers.timers[kind].generation != self.current['generation']
        elif kind=='dark_camera':return not c.timers.dark
        elif kind=='fatigue':return c.timers.in_break
        if good:
            if self.recovered_since is None:self.recovered_since=now
            return now-self.recovered_since>=3
        self.recovered_since=None
        return False

    def user_action(self, action, kind):
        self.trace('human_control', action=action, goal=kind)
        if self.current and kind in (self.current['goal'], 'agent_break'):
            self.current['blocked']=action in ('dismiss','acknowledge')
            if action=='snooze':self.current['stage']=0
        self.shown=None

    def step(self, candidate, c):
        now=c.timers.now
        if c.phase!='running' or c.calibrating:
            self.shown=None; return None
        # Keep goal and evidence through tracking loss; never mark unknown resolved.
        resolved=self.outcome(c,now)
        if resolved:
            goal=self.current['goal']
            source=c.last_drink_source if goal=='water' else 'opencv_pose' if goal=='posture' else 'face_landmarks' if goal=='distance' else 'timer_or_user_action'
            self.trace('goal_resolved', goal=goal, evidence={'posture':c.posture,'distance':c.signals.distance,'source':source})
            self.completed.add((self.current['goal'],self.current['generation']))
            self.current=None; self.shown=None; self.recovered_since=None
        if candidate and tuple(candidate) in self.completed:candidate=None
        if candidate and (not self.current or (candidate[0], candidate[1]) != (self.current['goal'],self.current['generation'])):
            if self.current:self.trace('goal_preempted', goal=self.current['goal'], next_goal=candidate[0])
            key=tuple(candidate)
            self.current=self.goals.setdefault(key,{'goal':candidate[0], 'generation':candidate[1], 'stage':0, 'at':now, 'blocked':False})
            self.recovered_since=None;self.last_decision=None;self.shown=None
        if not self.current:self.status='Waiting for observations';return None
        v=self.current;goal=v['goal']
        usable=bool(candidate and (candidate[0],candidate[1])==(goal,v['generation']))
        if goal=='posture':usable=usable and c.posture=='LOWER_HEAD_POSITION'
        if goal=='distance':usable=usable and c.signals.previous_valid
        if v['blocked']:self.status='Dismissed by you; observing outcome';self.shown=None;return None
        observation={'goal':goal,'stage':v['stage'],'meeting':c.meeting_active,'quiet':c.quiet,
                     'usable':usable,'resolved':False,'overdue':now-v['at']>=self.delay}
        # Human control and missing evidence are enforced immediately, even while
        # AWS is unavailable; only actionable policy decisions wait for the cloud.
        if c.quiet or c.meeting_active or not usable:
            decision,source=decide(observation),'local_safety'
        else:decision,source=self.cloud.choose(observation)
        if decision is None:self.status='Waiting for cloud policy';return self.shown if usable else None
        key=(goal,v['generation'],decision['action'],source)
        if key!=self.last_decision:
            self.trace('decision', observation=observation, evidence={'opencv_posture':c.posture,'distance':c.signals.distance,'drinking':c.drinking_status}, decision=decision, source=source)
            self.last_decision=key
        action=decision['action'];self.status=decision['reason']
        if action in ('defer','observe'):self.shown=None
        elif action=='remind':
            v['stage']=1;v['at']=now;self.shown=(goal,v['generation'])
            self.trace('tool_called', tool='show_reminder', goal=goal)
        elif action=='offer_break':
            v['stage']=2;self.shown=('agent_break',f"{goal}:{v['generation']}")
            self.trace('tool_called', tool='offer_break', goal=goal, reason='Visual position did not recover')
        elif action=='wait' and usable and self.shown is None:
            self.shown=('agent_break',f"{goal}:{v['generation']}") if v['stage']==2 else (goal,v['generation'])
        return self.shown

    def snapshot(self):
        return {'status':self.status,'cloud':self.cloud.status,'goal':self.current,'trace':self.rows[-40:]}
