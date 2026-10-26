import json
import math
from copy import deepcopy

DEFAULTS = {
    'straw_assist': {'enabled': False},
    'automatic_meeting': {'enabled': False},
    'automatic_drinking': {'enabled': True},
    'distance': {'enabled': True, 'size_ratio': 1.25, 'hold_seconds': 20},
    'fatigue': {'enabled': True, 'warmup_seconds': 10800, 'closure_seconds': 1.5},
    'posture': {'enabled': True, 'window_seconds': 1200},
    'water': {'enabled': True, 'interval_seconds': 3600},
    'movement': {'enabled': True, 'interval_seconds': 3600},
    'eyes': {'enabled': True, 'interval_seconds': 7200},
    'sleep': {'enabled': True, 'interval_seconds': 86400},
    'dark_camera': {'enabled': True, 'brightness_threshold': 35, 'hold_seconds': 5},
    'break_seconds': 1800, 'snooze_seconds': 300,
}


def load_settings(path, demo=False):
    config = deepcopy(DEFAULTS)
    if path.exists():
        raw = json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(raw, dict): raise ValueError('Settings must be a JSON object')
        for key, value in raw.items():
            if key not in config: raise ValueError(f'Unknown setting: {key}')
            if isinstance(config[key], dict):
                if not isinstance(value, dict): raise ValueError(f'{key} must be an object')
                for name, item in value.items():
                    if name not in config[key]: raise ValueError(f'Unknown setting: {key}.{name}')
                    config[key][name] = item
            else: config[key] = value
    for key, section in config.items():
        entries = section.items() if isinstance(section, dict) else [(key, section)]
        for name, value in entries:
            if name == 'enabled':
                if type(value) is not bool: raise ValueError(f'{key}.enabled must be true or false')
            elif isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError(f'{key}.{name} must be a positive finite number')
    if config['dark_camera']['brightness_threshold'] > 245:
        raise ValueError('Camera brightness threshold must be at most 245')
    if not 1.1<=config['distance']['size_ratio']<=2:
        raise ValueError('Relative face-size threshold must be between 1.1 and 2')
    if config['fatigue']['closure_seconds']<1:
        raise ValueError('Eye-closure threshold must be at least one second')
    if demo:
        for name, seconds in [('water',60),('movement',90),('eyes',120),('sleep',180)]:
            config[name]['interval_seconds'] = seconds
        config['posture']['window_seconds'] = 20
        config['break_seconds'] = 15
        config['snooze_seconds'] = 10
        config['distance']['hold_seconds'] = 3
        config['fatigue']['warmup_seconds'] = 30
    return config
