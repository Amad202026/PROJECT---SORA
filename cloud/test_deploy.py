import json
from io import BytesIO
import unittest
from unittest.mock import Mock
from agent_policy import decide
from cloud.deploy import verify_policy


class VerificationTests(unittest.TestCase):
    def client(self):
        client=Mock()
        def invoke(**kwargs):
            value=json.loads(kwargs['Payload'])
            return {'StatusCode':200,'Payload':BytesIO(json.dumps(decide(value)).encode()),
                    'ResponseMetadata':{'RequestId':'test-only-id'}}
        client.invoke.side_effect=invoke
        return client

    def test_verifies_all_eight_policy_paths(self):
        client=self.client();rows=verify_policy(client,'test-function')
        self.assertEqual(len(rows),8)
        self.assertEqual({r['response']['action'] for r in rows},{'remind','wait','offer_break','defer','observe','resolved'})
        self.assertEqual(client.invoke.call_count,8)

    def test_function_error_fails_verification(self):
        client=Mock();client.invoke.return_value={'Payload':BytesIO(b'{}'),'FunctionError':'Unhandled'}
        with self.assertRaisesRegex(RuntimeError,'invocation failed'):verify_policy(client,'test-function')

    def test_wrong_action_fails_verification(self):
        client=Mock();client.invoke.return_value={'StatusCode':200,'Payload':BytesIO(b'{"action":"resolved"}')}
        with self.assertRaisesRegex(RuntimeError,'mismatch'):verify_policy(client,'test-function')

    def test_missing_request_id_fails_verification(self):
        client=self.client();original=client.invoke.side_effect
        def no_id(**kwargs):
            response=original(**kwargs);response.pop('ResponseMetadata');return response
        client.invoke.side_effect=no_id
        with self.assertRaisesRegex(RuntimeError,'request ID'):verify_policy(client,'test-function')


if __name__=='__main__':unittest.main()
