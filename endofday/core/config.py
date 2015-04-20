"""
Read config files from:
- Deployed endofday.conf inside package
- /etc/endofday.conf
- /endofday.conf

"""

import ConfigParser
import os

from .error import Error

HERE = os.path.dirname(os.path.abspath((__file__)))

def read_config():
    parser = ConfigParser.ConfigParser()
    places = [os.path.abspath(os.path.join(HERE, '../endofday.conf')),
              os.path.expanduser('/etc/endofday.conf'),
              '/endofday.conf']
    if not parser.read(places):
        raise Error("couldn't read config file from {0}"
                           .format(', '.join(places)))
    return parser

def audit_config():
    platform = Config.get('execution', 'execution')
    if not platform:
        raise Error('Invalid config - execution.platform is required.')
    if not platform == 'localhost' and not platform == 'agave':
        raise Error('Invalid config - execution.platform must be either "localhost" or "agave".')

Config = read_config()
audit_config()