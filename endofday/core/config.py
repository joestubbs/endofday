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
    places = ['/endofday.conf',
              os.path.abspath(os.path.join(HERE, '../endofday.conf')),
              '/host/etc/endofday.conf',
              '/staging/endofday.conf',
              '/host/home/eod/endofday.conf',
              ]
    if not parser.read(places):
        raise Error("couldn't read config file from {0}"
                           .format(', '.join(places)))
    return parser

Config = read_config()