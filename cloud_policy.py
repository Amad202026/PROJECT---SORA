"""Optional IAM-authenticated cloud decisions; bounded asynchronous local fallback."""
import json
import time
from pathlib import Path
from threading import Thread, Lock
from agent_policy import decide, ACTIONS, POLICY_VERSION


class CloudPolicy:
    def __init__(self, root):
        self.config = {}; self.status = 'Local policy'; self.lock = Lock()
        self.pending = None; self.result = None; self.started = 0.; self.retry_at = 0.
        self.client = None
        path = Path(root) / 'cloud_config.json'
        if path.exists():
            try:
                config = json.loads(path.read_text())
                if config.get('enabled') is True:
                    if not config.get('function_name') or not config.get('region'):
                        raise ValueError('Missing cloud target')
                    self.config = config; self.status = 'AWS configured; awaiting decision'
            except (ValueError, OSError, AttributeError): self.status = 'Invalid cloud config; local policy'

    def _invoke(self, key, value):
        try:
            if self.client is None:
                import boto3
                from botocore.config import Config
                session = boto3.Session(profile_name=self.config.get('profile') or None, region_name=self.config['region'])
                self.client = session.client('lambda', config=Config(connect_timeout=2, read_timeout=3, retries={'max_attempts': 0}))
            response = self.client.invoke(FunctionName=self.config['function_name'], InvocationType='RequestResponse', Payload=json.dumps(value).encode())
            if response.get('FunctionError'): raise ValueError('Cloud function rejected the observation')
            raw = response['Payload'].read(8193)
            if len(raw) > 8192: raise ValueError('Cloud response too large')
            answer = json.loads(raw)
            if answer.get('policy') != POLICY_VERSION or answer.get('action') not in ACTIONS:
                raise ValueError('Unsupported cloud policy response')
            # Constrain remote tools to the audited policy contract. A compromised
            # response cannot override quiet mode or invent recovery.
            if answer != decide(value): raise ValueError('Cloud decision failed safety validation')
            with self.lock:
                self.result = (key, answer); self.status = 'AWS policy connected'
        except Exception as exc:
            with self.lock:
                self.result = (key, None); self.retry_at = time.monotonic() + 60
                self.status = 'AWS unavailable; local fallback (' + type(exc).__name__ + ')'
        finally:
            with self.lock: self.pending = None

    def choose(self, value):
        if not self.config: return decide(value), 'local'
        key = json.dumps(value, sort_keys=True); now = time.monotonic()
        with self.lock:
            if self.result and self.result[0] == key:
                if self.result[1]:return self.result[1], 'aws'
                if now < self.retry_at:return decide(value), 'local_fallback'
                self.result=None
            if now < self.retry_at: return decide(value), 'local_fallback'
            if self.pending is None:
                self.pending = key; self.started = now
                Thread(target=self._invoke, args=(key, dict(value)), daemon=True).start()
            # Do not consume a decision for a different observation. Camera/UI
            # keep running while the cloud request is pending.
            if now - self.started < 3: return None, 'aws_pending'
            return decide(value), 'local_fallback'
