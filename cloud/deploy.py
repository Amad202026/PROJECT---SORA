"""Build, review, deploy, verify, or remove the optional AWS policy component."""
from pathlib import Path
import argparse
import json
import re
import sys
import time
import hashlib
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parent.parent


def verify_policy(client, arn):
    """Real Lambda calls using synthetic observations, not camera-accuracy data."""
    sys.path.insert(0,str(ROOT))
    from agent_policy import decide
    base={'goal':'posture','stage':0,'meeting':False,'quiet':False,'usable':True,'resolved':False,'overdue':False}
    scenarios=[
        ('first_reminder',{}),
        ('wait_without_spam',{'stage':1}),
        ('offer_break_if_unresolved',{'stage':1,'overdue':True}),
        ('stop_escalating',{'stage':2,'overdue':True}),
        ('quiet_mode',{'quiet':True}),
        ('meeting',{'meeting':True}),
        ('missing_visual_evidence',{'usable':False}),
        ('resolved',{'resolved':True}),
    ]
    rows=[]
    for name, overrides in scenarios:
        observation={**base,**overrides};started=time.perf_counter()
        response=client.invoke(FunctionName=arn,InvocationType='RequestResponse',Payload=json.dumps(observation).encode())
        stream=response['Payload']
        try:raw=stream.read(8193)
        finally:stream.close()
        if response.get('FunctionError'):raise RuntimeError('AWS policy invocation failed: '+name)
        if response.get('StatusCode')!=200 or len(raw)>8192:raise RuntimeError('Invalid AWS response: '+name)
        answer=json.loads(raw)
        if answer!=decide(observation):raise RuntimeError('AWS policy verification mismatch: '+name)
        request_id=response.get('ResponseMetadata',{}).get('RequestId')
        if not request_id:raise RuntimeError('Missing AWS request ID: '+name)
        rows.append({'scenario':name,'passed':True,'request_id':request_id,
                     'round_trip_ms':round((time.perf_counter()-started)*1000,2),
                     'observation':observation,'response':answer})
    return rows


def template():
    return {
        'AWSTemplateFormatVersion':'2010-09-09',
        'Description':'Sora optional IAM-only intervention policy. No camera or audio data.',
        'Resources':{
            'PolicyLogs':{'Type':'AWS::Logs::LogGroup','Properties':{
                'LogGroupName':{'Fn::Sub':'/aws/lambda/${AWS::StackName}-policy'},'RetentionInDays':7}},
            'PolicyRole':{'Type':'AWS::IAM::Role','Properties':{
                'AssumeRolePolicyDocument':{'Version':'2012-10-17','Statement':[{
                    'Effect':'Allow','Principal':{'Service':'lambda.amazonaws.com'},'Action':'sts:AssumeRole'}]},
                'Policies':[{'PolicyName':'WriteOwnLogs','PolicyDocument':{'Version':'2012-10-17','Statement':[{
                    'Effect':'Allow','Action':['logs:CreateLogStream','logs:PutLogEvents'],
                    'Resource':{'Fn::GetAtt':['PolicyLogs','Arn']}}]}}]}},
            'PolicyFunction':{'Type':'AWS::Lambda::Function','Properties':{
                'FunctionName':{'Fn::Sub':'${AWS::StackName}-policy'},'Runtime':'python3.12',
                'Handler':'index.handler','MemorySize':128,'Timeout':3,
                'Role':{'Fn::GetAtt':['PolicyRole','Arn']},
                'Code':{'ZipFile':(ROOT/'agent_policy.py').read_text(encoding='utf-8')}}}},
        'Outputs':{'FunctionArn':{'Value':{'Fn::GetAtt':['PolicyFunction','Arn']}}}
    }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','identity','deploy','verify','delete'])
    parser.add_argument('--region',default='ap-southeast-1');parser.add_argument('--profile')
    parser.add_argument('--stack',default='sora-companion');parser.add_argument('--account')
    args=parser.parse_args()
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9-]{0,40}',args.stack):parser.error('Invalid stack name')
    body=json.dumps(template(),indent=2)
    if args.action in ('prepare','deploy'):
        (ROOT/'cloud/template.json').write_text(body,encoding='utf-8')
    if args.action=='prepare':print('Prepared cloud/template.json. No AWS resources created.');return
    import boto3
    session=boto3.Session(profile_name=args.profile,region_name=args.region)
    identity=session.client('sts').get_caller_identity()
    if args.action=='identity':print(json.dumps({'account':identity['Account'],'region':args.region}));return
    if args.account!=identity['Account']:parser.error('Pass --account with the intended AWS account ID; no changes made.')
    cf=session.client('cloudformation')
    if args.action=='delete':
        cf.delete_stack(StackName=args.stack);cf.get_waiter('stack_delete_complete').wait(StackName=args.stack)
        (ROOT/'cloud_config.json').write_text('{"enabled":false}')
        print('Stack removed. Local mode restored.');return
    if args.action=='deploy':
        exists=False
        try:cf.describe_stacks(StackName=args.stack);exists=True
        except cf.exceptions.ClientError as exc:
            if 'does not exist' not in str(exc):raise
        arguments=dict(StackName=args.stack,TemplateBody=body,Capabilities=['CAPABILITY_IAM'])
        if exists:
            try:cf.update_stack(**arguments)
            except cf.exceptions.ClientError as exc:
                if 'No updates are to be performed' not in str(exc):raise
            else:cf.get_waiter('stack_update_complete').wait(StackName=args.stack)
        else:
            cf.create_stack(**arguments,Tags=[{'Key':'Project','Value':'Sora'}])
            cf.get_waiter('stack_create_complete').wait(StackName=args.stack)
    stack=cf.describe_stacks(StackName=args.stack)['Stacks'][0]
    if stack['StackStatus'] not in ('CREATE_COMPLETE','UPDATE_COMPLETE'):raise RuntimeError('Stack is not ready')
    arn=next(x['OutputValue'] for x in stack['Outputs'] if x['OutputKey']=='FunctionArn')
    from botocore.config import Config
    client=session.client('lambda',config=Config(connect_timeout=5,read_timeout=10,retries={'max_attempts':0}))
    rows=verify_policy(client,arn)
    config={'enabled':True,'region':args.region,'profile':args.profile,'function_name':arn}
    (ROOT/'cloud_config.json').write_text(json.dumps(config,indent=2))
    receipt={'verified_at':datetime.now(timezone.utc).isoformat(),'region':args.region,'stack':args.stack,
             'function':arn,'evidence_type':'real_aws_invocations_with_synthetic_policy_inputs',
             'not_camera_accuracy':True,'passed':len(rows),'total':len(rows),'cases':rows,
             'local_policy_sha256':hashlib.sha256((ROOT/'agent_policy.py').read_bytes()).hexdigest()}
    (ROOT/'cloud/deployment_receipt.json').write_text(json.dumps(receipt,indent=2))
    caller={'Version':'2012-10-17','Statement':[{'Effect':'Allow','Action':'lambda:InvokeFunction','Resource':arn}]}
    (ROOT/'cloud/runtime_iam_policy.json').write_text(json.dumps(caller,indent=2))
    print(f'AWS policy verified: {len(rows)}/{len(rows)} scenarios. Restart Sora to load cloud_config.json. Receipt: cloud/deployment_receipt.json.')

if __name__=='__main__':main()
