from argparse import ArgumentParser
import random

import ConfigParser
import os

HERE = os.path.dirname(os.path.abspath((__file__)))

class AgaveConfigParser(ConfigParser.ConfigParser):
    def get(self, section, option, raw=False, vars=None, default_value=None):
        try:
            return ConfigParser.ConfigParser.get(self, section, option, raw, vars)
        except ConfigParser.NoOptionError:
            return default_value

def read_config(path):
    parser = AgaveConfigParser()
    places = [path]
    if not parser.read(places):
        return None
    return parser


def from_config(args):
    config = read_config(args.path)
    args.coords = config.get('genpoints', 'coords')
    args.files = config.get('genpoints', 'files')
    return args

def genpoints(n, f):
    """
    Generates n coordinates into t output files labeled 
    """
    for i in range(f):
        out = open('/data/out_' + str(i), 'w')
        for j in range(n):
            x = random.random()
            y = random.random()
            out.write(str(x) + ',' + str(y) + '\n')
        out.close()

def main():
    parser = ArgumentParser(description="generate random coordinates.")
    parser.add_argument('-v', '--version', action='version', version="0.1")
    parser.add_argument('-n', '--coords', help='number of coords to generate per file') 
    parser.add_argument('-f', '--files', help='number of files to generate')
    parser.add_argument('-p', '--path', help='path to config file.')
    args = parser.parse_args()
    if args.path:
        args = from_config(args)
    # supply defaults
    if not args.coords:
        args.coords = 1000
    if not args.files:
        args.files = 4
    genpoints(int(args.coords), int(args.files))

if __name__ == "__main__":
    main()

