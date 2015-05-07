from argparse import ArgumentParser
import decimal
from os import listdir
from os.path import isfile, join
import random

def apprxpi(path):
    """
    approxmates pi by accumulating totals of points inside and out of a circle. 
    """
    incirc = 0
    tot = 0
    files = [ join(path,f) for f in listdir(path) if isfile(join(path,f)) ]
    out = open('/tmp/pi', 'w')
    for f in files:
        with open (f, 'rb') as inp:
            for line in inp:
                parts = line.split(',')
                x = decimal.Decimal(parts[0].strip())
                y = decimal.Decimal(parts[1].strip())
                incirc += x
                tot += y
    pi = 4.0 * float(incirc) / float(tot)
    print pi
    out.write(str(pi))
    out.close()

def main():
    parser = ArgumentParser(description="count coordinates in a circle.")
    parser.add_argument('-v', '--version', action='version', version="0.1")
    parser.add_argument('-p', '--path', help='path to input files to process')    
    args = parser.parse_args()
    apprxpi(args.path)

if __name__ == "__main__":
    main()

