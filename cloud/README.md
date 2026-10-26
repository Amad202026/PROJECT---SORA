# AWS policy deployment

For a new account, follow [MULAI_AWS.md](MULAI_AWS.md) first. Browser login uses
AWS CLI v2 (minimum 2.32.0) and the pinned `awscrt` dependency in requirements.txt.

Status in the distributed package: **prepared, not deployed**. A successful local
test is not evidence of an AWS deployment. `deployment_receipt.json` is generated
only by a successful real AWS invocation.

The substantive cloud component selects the next intervention from derived
OpenCV observations and the current goal stage. The desktop executes only the
audited action set, observes the outcome, and requests a subsequent decision.
This is a deterministic policy agent, not an LLM. In local mode the same policy
executes on the desktop. No COOL claim is made.

## Resources and privacy

- One Python 3.12 Lambda (128 MB, 3-second timeout), one execution role, one log
  group (7-day retention). No database, public URL, API Gateway, NAT or video upload.
- Requests contain goal, stage and five booleans. Logs contain only policy action.
- IAM authentication uses the standard AWS SDK credential chain. Prefer a local
  SSO profile and a runtime role restricted to `lambda:InvokeFunction` on this function.
  Never paste credentials into code, chat, Git or the submission archive.
- The runtime needs outbound AWS access. A timeout falls back locally after
  three seconds without stopping the camera. Failure retries are delayed 60 seconds.
- A response for stale evidence is ignored. Human quiet mode, unavailable vision,
  and meeting suppression are enforced immediately on-device.
- AWS usage and logs may incur charges; free credits are account-dependent.
  Inspect the template before deployment, configure a budget in your AWS account,
  and remove the stack after judging. There is no promise of a zero bill.

## Commands (PowerShell, from the application directory)

```powershell
.\.venv\Scripts\python.exe -m pip install -r cloud\requirements.txt
.\.venv\Scripts\python.exe cloud\deploy.py prepare
.\.venv\Scripts\python.exe cloud\deploy.py identity --profile YOUR_SSO_PROFILE
```

Review `cloud/template.json`. Authenticate your profile using your organization's
AWS login process. Replace the profile and account arguments below with your own
values. Deployment creates billable resources and an IAM execution role:

```powershell
.\.venv\Scripts\python.exe cloud\deploy.py deploy --profile YOUR_SSO_PROFILE --account YOUR_ACCOUNT_ID --region ap-southeast-1
.\.venv\Scripts\python.exe cloud\deploy.py verify --profile YOUR_SSO_PROFILE --account YOUR_ACCOUNT_ID --region ap-southeast-1
```

Deployment/verification calls Lambda with eight synthetic policy scenarios and
stores request IDs, responses and round-trip latency in deployment_receipt.json.
These are real cloud invocations after authentication, not camera-accuracy tests.
The configuration is enabled only after all eight responses pass verification.

After successful verification, fully restart Sora and open **Agent activity**.
Record a trace whose decision source is `aws`, then disconnect AWS and demonstrate
`local_fallback`. Use the generated `runtime_iam_policy.json` to restrict the runtime
identity. Deployment identity needs CloudFormation, Lambda, IAM role creation/pass
and log-group permissions; do not distribute that identity to judges.

```powershell
.\.venv\Scripts\python.exe cloud\deploy.py delete --profile YOUR_SSO_PROFILE --account YOUR_ACCOUNT_ID --region ap-southeast-1
```

This removes only the named stack and restores local mode. Use the same region
and stack arguments you deployed with. Review the stack in AWS before deleting.

Official references:
- https://docs.aws.amazon.com/lambda/latest/api/API_Invoke.html
- https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-lambda-function.html
- https://docs.aws.amazon.com/sdkref/latest/guide/standardized-credentials.html
- https://aws.amazon.com/lambda/pricing/
