"""Deterministic synthetic policy scenarios. This does not measure vision accuracy."""
from pathlib import Path
from copy import deepcopy
import json
from session_controller import SessionController
from timer_settings import DEFAULTS


def run():
    cases=[];traces=[]
    for scenario in ('recover','persistent_position','tracking_lost','meeting','dismiss','water_correction'):
        c=SessionController(Path('.'),deepcopy(DEFAULTS),demo=True,persist=False);c.start();c.agent.cloud.config={}
        c.timers.present=True;c.posture='LOWER_HEAD_POSITION';c.timers.set_posture(True)
        if scenario=='meeting':c.meeting_active=True
        if scenario=='water_correction':c.timers.set_posture(False);c.timers.timers['water'].elapsed=4000
        first=c.notice()
        if scenario=='dismiss':c.notice_action('dismiss','posture')
        for t in range(1,20):
            c.timers.now=t
            if scenario=='recover' and t>=3:c.posture='NEAR_REFERENCE';c.timers.set_posture(False)
            if scenario=='tracking_lost':c.posture='UNKNOWN';c.timers.present=False
            if scenario=='water_correction' and t==5:c.record_drink()
            c.notice()
        rows=c.agent.rows;tools=[r['tool'] for r in rows if r['event']=='tool_called']
        recovered=any(r['event']=='goal_resolved' for r in rows)
        expected={'recover':(['show_reminder'],True),'persistent_position':(['show_reminder','offer_break'],False),
                  'tracking_lost':(['show_reminder'],False),'meeting':([],False),
                  'dismiss':(['show_reminder'],False),'water_correction':(['show_reminder'],True)}[scenario]
        cases.append({'scenario':scenario,'passed':(tools,recovered)==expected,'tools':tools,'resolved':recovered})
        traces.extend({'scenario':scenario,'data_type':'synthetic_policy_input',**r} for r in rows)
    root=Path(__file__).resolve().parent/'evaluation';root.mkdir(exist_ok=True)
    report={'data_type':'synthetic_policy_scenarios_not_camera_accuracy','passed':sum(r['passed'] for r in cases),'total':len(cases),'cases':cases}
    (root/'policy_results.json').write_text(json.dumps(report,indent=2))
    (root/'policy_trace.jsonl').write_text('\n'.join(json.dumps(r) for r in traces))
    print(json.dumps(report,indent=2))
    if not all(r['passed'] for r in cases):raise SystemExit(1)

if __name__=='__main__':run()
