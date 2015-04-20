import sys

class Error(Exception):
    def __init__(self, msg = None):
        self.msg = msg
        sys.exit(msg)

