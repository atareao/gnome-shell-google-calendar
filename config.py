'''
Created on 17.02.2012

@author: flocki
'''
import json
import os

local_config_dir = os.getenv('HOME') + '/.config/gnome-shell-google-calendar/'
global_config_dir = '/etc/gnome-shell-google-calendar/'

def set(parameter, value):
    config = get(None)
    config[parameter] = value
    if not os.path.exists(local_config_dir):
      os.makedirs(local_config_dir)
    with open(local_config_dir + 'config.json', 'w') as fp:
        json.dump(config, fp)


def get(parameter):
    try:
        with open(local_config_dir + 'config.json', 'r') as fp:
            config = json.load(fp)
    except:
        config = dict()

    if parameter is None:
        return config
    if parameter in config:
        return config.get(parameter)
    else:
        config[parameter] = None
