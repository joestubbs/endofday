
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
    places = ['/host/home/eod/endofday.conf',
              '/staging/endofday.conf',
              '/host/etc/endofday.conf',
              os.path.abspath(os.path.join(HERE, '../endofday.conf')),
              '/endofday.conf',
              ]
    place = places[0]
    for p in places:
        if os.path.exists(p):
            place = p
            break
    if not parser.read(place):
        raise Error("couldn't read config file from {0}"
                           .format(', '.join(places)))
    return parser

Config = read_config()