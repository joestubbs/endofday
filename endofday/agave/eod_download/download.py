# This script downloads an Agave file to the local system.
#
# usage: python download.py
#
# This script looks for a single file in the /agave/inputs directory whose name is 1
# and whose contents are the URI or agave URL to download. Downloads file to /agave/outputs/1

from __future__ import print_function
import os
import sys

sys.path.append('/')

from agavepy.agave import Agave

from core.error import Error


HERE = os.path.dirname(os.path.abspath((__file__)))

JOB_TEMPLATE = '/job.j2'

VERIFY = False

def get_uri():
    with open('/agave/inputs/1') as f:
        uri = f.readline().strip('\n')
    return uri


def main():
    uri = get_uri()
    access_token = os.environ.get('access_token')
    refresh_token = os.environ.get('refresh_token')
    if not access_token:
        raise Error("access_token required.")
    if not refresh_token:
        raise Error("refresh_token required.")
    print("using access_token: {}".format(access_token))
    print("using refresh_token: {}".format(refresh_token))

    api_server = os.environ.get('api_server')
    if not api_server:
        raise Error("api_server required.")
    print("using api_server: {}".format(api_server))

    verify = os.environ.get('verify')
    if verify == 'False':
        verify = False
    else:
        verify = True
    print("using verify: {}".format(verify))

    api_key = os.environ.get('api_key')
    if not api_key:
        raise Error("api_key required.")
    print("using api_key: {}".format(api_key))

    api_secret = os.environ.get('api_secret')
    if not api_secret:
        raise Error("api_secret required.")
    print("using api_secret: {}".format(api_secret))

    ag = Agave(api_server=api_server,
               api_key=api_key,
               api_secret=api_secret,
               token=access_token,
               refresh_token=refresh_token,
               verify=verify)

    try:
        rsp = ag.download_uri(uri, '/agave/outputs/1')
    except Exception as e:
        print("Error trying to download file: {}. Exception: {}".format(uri, e))
        raise e
    print("Download complete.")


if __name__ == '__main__':
    main()