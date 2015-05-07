from argparse import ArgumentParser
import decimal
import random

def ctpoints(path):
    """
    count coordinates in a cirle from an input file. 
    """
    incirc = 0
    tot = 0
    out = open('/tmp/output', 'w')
    with open (path, 'rb') as f:
        for line in f:
 #           try:
                parts = line.split(',')
                x = decimal.Decimal(parts[0].strip())
                y = decimal.Decimal(parts[1].strip())
                if x*x + y*y <= 1:
                    incirc += 1
                tot += 1
#            except Exception as e:
#                print "Got an exception:", str(e)
#                raise e
    out.write(str(incirc) + ',' + str(tot))
    out.close()

def main():
    parser = ArgumentParser(description="count coordinates in a circle.")
    parser.add_argument('-v', '--version', action='version', version="0.1")
    parser.add_argument('-p', '--path', help='path to input file to process')    
    args = parser.parse_args()
    ctpoints(args.path)

if __name__ == "__main__":
    main()

