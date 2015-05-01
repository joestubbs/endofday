import json
import os
import sys

HERE = os.path.dirname(os.path.abspath((__file__)))
sys.path.append(os.path.abspath(os.path.join(HERE, '..', '..')))

from endofday.core.executors import AgaveExecutor

def main():
    ae = AgaveExecutor(wf_name='register_endofday_agave')
    systems = ['/home/jstubbs/github-repos/endofday/endofday/agave/endofday-exec/endofday-exec.json',
               '/home/jstubbs/github-repos/endofday/endofday/agave/endofday-stor/endofday-stor.json']
    for s in systems:
        print "Registering system:", os.path.split(s)[1]
        rsp = ae.ag.systems.add(body=json.load(open(s, 'rb')))
        print "Response:", str(rsp)
    app = '/home/jstubbs/github-repos/endofday/endofday/agave/endofday-app/app.json'
    print "Registering app:", os.path.split(app)[1]
    rsp = ae.ag.apps.add(body=json.load(open(app, 'rb')))
    print "Response:", str(rsp)

if __name__ == "__main__":
    main()