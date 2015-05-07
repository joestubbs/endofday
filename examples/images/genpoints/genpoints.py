from argparse import ArgumentParser
import decimal
import random

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
    args = parser.parse_args()
    if not args.coords:
        args.coords = 1000
    if not args.files:
        args.files = 4
    genpoints(int(args.coords), int(args.files))

if __name__ == "__main__":
    main()

