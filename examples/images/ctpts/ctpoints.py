from argparse import ArgumentParser
import decimal
import os

def ctpoints(path):
    """
    count coordinates in a cirle from an input file or directory.
    """
    incirc = 0
    tot = 0
    out = open('/tmp/output', 'w')
    # if they passed a directory, process all files at the top level
    if os.path.isdir(path):
        for _, _, fnames in os.walk(path):
            files = [os.path.join(path, f) for f in fnames]
            break
    else:
        files = [path]
    print "Reading these files:"
    for f in files:
        print f
    for f in files:
        with open (f, 'rb') as f:
            for line in f:
                parts = line.split(',')
                x = decimal.Decimal(parts[0].strip())
                y = decimal.Decimal(parts[1].strip())
                if x*x + y*y <= 1:
                    incirc += 1
                tot += 1
    out.write(str(incirc) + ',' + str(tot))
    out.close()

def main():
    parser = ArgumentParser(description="count coordinates in a circle.")
    parser.add_argument('-v', '--version', action='version', version="0.1")
    parser.add_argument('-p', '--path', help='path to input file or directory to process')
    args = parser.parse_args()
    ctpoints(args.path)

if __name__ == "__main__":
    main()

