from io import BytesIO
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch
from cloud_policy import CloudPolicy
from agent_policy import decide
from cloud.deploy import template
from evaluate_video import score_events
import test_agent


class DeliveryTests(unittest.TestCase):
    def observation(self):return {'goal':'posture','stage':1,'meeting':False,'quiet':False,'usable':True,'resolved':False,'overdue':True}
    def test_cloud_success_and_stale_reply(self):
        p=CloudPolicy('.');p.config={'function_name':'test'};value=self.observation()
        p.client=Mock();p.client.invoke.return_value={'Payload':BytesIO(json.dumps(decide(value)).encode())}
        key=json.dumps(value,sort_keys=True);p._invoke(key,value)
        self.assertEqual(p.choose(value)[1],'aws')
        changed={**value,'quiet':True}
        with patch('cloud_policy.Thread'):
            self.assertEqual(p.choose(changed),(None,'aws_pending'))
    def test_cloud_failure_local_fallback(self):
        p=CloudPolicy('.');p.config={'function_name':'test'};value=self.observation();p.client=Mock()
        p.client.invoke.side_effect=TimeoutError();p._invoke(json.dumps(value,sort_keys=True),value)
        result,source=p.choose(value);self.assertEqual(source,'local_fallback');self.assertEqual(result,decide(value))
    def test_cloud_invalid_action_rejected(self):
        p=CloudPolicy('.');p.config={'function_name':'test'};v=self.observation();p.client=Mock()
        p.client.invoke.return_value={'Payload':BytesIO(b'{"policy":"sora-policy-1","action":"resolved","reason":"lie"}')}
        p._invoke(json.dumps(v,sort_keys=True),v);self.assertEqual(p.choose(v)[1],'local_fallback')
    def test_cloud_failure_retry_after_cooldown(self):
        p=CloudPolicy('.');p.config={'function_name':'test'};v=self.observation()
        p.result=(json.dumps(v,sort_keys=True),None);p.retry_at=0
        with patch('cloud_policy.Thread') as thread:
            self.assertEqual(p.choose(v)[1],'aws_pending');thread.assert_called_once()
    def test_template_is_iam_only_no_public_endpoint(self):
        t=template();types=[r['Type'] for r in t['Resources'].values()]
        self.assertEqual(types.count('AWS::Lambda::Function'),1)
        self.assertNotIn('AWS::Lambda::Url',types)
        code=t['Resources']['PolicyFunction']['Properties']['Code']['ZipFile']
        namespace={};exec(compile(code,'index.py','exec'),namespace)
        self.assertEqual(namespace['handler'](self.observation(),None),decide(self.observation()))
    def test_metrics_count_duplicate_and_miss(self):
        m=score_events([3,3.5,20],[(1,3),(10,13)])
        self.assertEqual((m['true_positive'],m['false_positive_including_duplicates'],m['false_negative']),(1,2,1))
        self.assertIsNone(score_events([],[])['recall']);self.assertIsNone(score_events([],[])['precision'])
    def test_preemption_does_not_restart_first_intervention(self):
        c=test_agent.AgentTests().controller();c.notice();c.timers.timers['water'].elapsed=4000;c.notice()
        c.record_drink();c.notice()
        tools=[r for r in c.agent.rows if r.get('tool')=='show_reminder' and r.get('goal')=='posture']
        self.assertEqual(len(tools),1)


if __name__=='__main__':unittest.main()
