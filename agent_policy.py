"""Versioned, deterministic intervention policy shared by desktop and AWS Lambda.

No diagnosis, arbitrary tool execution, images, or language model required.
"""
POLICY_VERSION = 'sora-policy-1'
GOALS = {'posture', 'distance', 'water', 'movement', 'eyes', 'sleep', 'fatigue', 'dark_camera', 'break_done'}
ACTIONS = {'defer', 'observe', 'remind', 'offer_break', 'resolved', 'wait'}


def validate_observation(value):
    required = {'goal', 'stage', 'meeting', 'quiet', 'usable', 'resolved', 'overdue'}
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError('Invalid observation fields')
    if value['goal'] not in GOALS or type(value['stage']) is not int or value['stage'] not in (0, 1, 2):
        raise ValueError('Invalid goal or stage')
    if any(type(value[k]) is not bool for k in required - {'goal', 'stage'}):
        raise ValueError('Observation flags must be boolean')
    return value


def decide(value):
    v = validate_observation(value)
    if v['resolved']:
        action, reason = 'resolved', 'Observed outcome or explicit user action completed the goal'
    elif v['quiet'] or v['meeting']:
        action, reason = 'defer', 'Respect manual quiet mode or possible meeting'
    elif not v['usable']:
        action, reason = 'observe', 'Wait for usable visual evidence; missing data is not recovery'
    elif v['stage'] == 0:
        action, reason = 'remind', 'Eligible observation warrants a first intervention'
    elif v['stage'] == 1 and v['overdue'] and v['goal'] in ('posture', 'distance'):
        action, reason = 'offer_break', 'Position has not recovered; offer an alternative action once'
    else:
        action, reason = 'wait', 'Continue observing without repeating the reminder'
    return {'policy': POLICY_VERSION, 'action': action, 'reason': reason}


def handler(event, context):
    # IAM-authenticated Lambda Invoke; intentionally no public function URL.
    result = decide(event)
    print('{"component":"sora-policy","action":"' + result['action'] + '"}')
    return result
