"""
Config files are read from the following places in order, with subsequent reads overwriting prior ones:
- /endofday.conf
- /etc/endofday.conf
- Deployed endofday.conf inside package
- When running in docker, an endofday.conf in the current working directory (mounted to /staging in the container).

"""

import ConfigParser
import os

from .error import Error

HERE = os.path.dirname(os.path.abspath((__file__)))

class AgaveConfigParser(ConfigParser.ConfigParser):
    def get(self, section, option, raw=False, vars=None, default_value=None):
        try:
            return ConfigParser.ConfigParser.get(self, section, option, raw, vars)
        except ConfigParser.NoOptionError:
            return default_value

def read_config():
    parser = AgaveConfigParser()
    print "contents of staging dir:", str(os.listdir('/staging'))
    places = ['/endofday.conf',
              os.path.expanduser('/etc/endofday.conf'),
              os.path.abspath(os.path.join(HERE, '../endofday.conf')),
              '/staging/endofday.conf',]
    if not parser.read(places):
        raise Error("couldn't read config file from {0}"
                           .format(', '.join(places)))
    return parser

def audit_config():
    platform = Config.get('execution', 'execution')
    if not platform:
        raise Error('Invalid config - execution.platform is required.')
    if not platform == 'local' and not platform == 'agave':
        raise Error('Invalid config - execution.platform must be either "local" or "agave".')

Config = read_config()
audit_config()