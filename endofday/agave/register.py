import json
import os
import sys


# Run this script to register the eod storage and compute system as well as the eod app. The 'sandbox'
# versions are running in Azure. Make sure to do the following before running:
#
# 1. update the password or private key value in the system json descriptions.
# 2. update the list of systems in the code below.
# 3. copy a valid eod.conf to /staging/endofday.conf for the tenant.
# 4. activate the eod virtualenv and run: python register.py

HERE = os.path.dirname(os.path.abspath((__file__)))
sys.path.append(os.path.abspath(os.path.join(HERE, '..', '..')))

from endofday.core.executors import AgaveExecutor

def main():
    ae = AgaveExecutor(wf_name='register_endofday_agave')
    systems = ['/home/jstubbs/github-repos/endofday/endofday/agave/endofday-stor/endofday-stor-sandbox.json',
               '/home/jstubbs/github-repos/endofday/endofday/agave/endofday-exec/endofday-exec-sandbox.json']
    for s in systems:
        print "Registering system:", os.path.split(s)[1]
        rsp = ae.ag.systems.add(body=json.load(open(s, 'rb')))
        print "Response:", str(rsp)
    app = '/home/jstubbs/github-repos/endofday/endofday/agave/endofday-app/app-sandbox.json'
    print "Registering app:", os.path.split(app)[1]
    rsp = ae.ag.apps.add(body=json.load(open(app, 'rb')))
    print "Response:", str(rsp)

if __name__ == "__main__":
    main()