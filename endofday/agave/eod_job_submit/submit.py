# This script submits a job to Agave as part of an eod workflow execution.
#
# usage: python submit.py app_id=<app_id> param_1=val_1 ... param_n=val_n
# where param_j is the id of a parameter to the Agave app with id app_id
#
# This script looks for files in the /agave/inputs directory whose names are the id's of the inputs
# and whose contents are the URIs to pass to the agave job.

# compiles a job template with the following:
#   app_id: the app to submit to
#   system_id: the system to archive to
#   inputs: list of objects with the following:
#       id: the id for the input
#       uris: list of objects with the following:
#           - uri_str: the full URI including quotes and trailing comma,
#                      e.g. "agave://example.orf//data/input.txt",
#
#   parameters: list of objects with the following:
#       id: the id for the parameter
#       value: the value for the parameter; this needs to be the proper JSON object with quotes and trailing commas.



from __future__ import print_function
import os
import sys

import jinja2

from agavepy.agave import Agave
from core.template import ConfigGen
from core.error import Error
from core.executors import AgaveAsyncResponse


HERE = os.path.dirname(os.path.abspath((__file__)))

JOB_TEMPLATE = '/job.j2'

API_KEY = ''

API_SECRET = ''

API_SERVER = ''

VERIFY = False

def get_inputs():
    """Returns a list of dictionaries of the form
    [ { 'id': <input_id>, 'uris': [<uri_1>, ...,<uri_n>] }]. """
    # immediate subdirectories are the input ids
    input_ids = [y for y in os.listdir('/agave/inputs') if os.path.isdir(y)]
    inputs = []
    for input_id in input_ids:
        uris = []
        for name in os.listdir(os.path.join('/agave/inputs/',input_id)):
            with open(os.path.join('/agave/inputs/',input_id, name), 'r') as f:
                uri = f.readline()
                if '://' in uri:
                    uris.append('"' + uri + '",')
        # remove trailing comma from last entry:
        uris[-1] = uris[-1][:-1]
        inputs.append({'id': input_id, 'uris': uris})
    return inputs

def get_outputs():
    """Reads /agave/outputs/output_labels file and returns a list of Agave outputs to look for
    after the job completes. The strings are either paths relative to the job work directory of
    output id's defined in the agave app description.
    """
    outputs = []
    with open('/agave/outputs/output_labels', 'r') as f:
        job_path_or_id = f.readline()
        outputs.append(job_path_or_id)
    return outputs

def submit_job(app_id, inputs, params, outputs, system_id,
               access_token, refresh_token):
    context = {'app_id': app_id, 'system_id': system_id}

    conf = ConfigGen(JOB_TEMPLATE)
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(HERE), trim_blocks=True, lstrip_blocks=True)
    job = conf.compile(context, env)
    ag = Agave(api_server=API_SERVER,
               api_key=API_KEY,
               api_secret=API_SECRET,
               token=access_token,
               refresh_token=refresh_token)
    rsp = ag.jobs.submit(body=job)
    return AgaveAsyncResponse(ag, rsp)


def main():
    args = dict([arg.split('=', 1) for arg in sys.argv[1:]])
    app_id = args.pop('app_id', None)
    if not app_id:
        raise Error("app_id is required.")
    params = args
    inputs = get_inputs()
    outputs = get_outputs()
    access_token = os.environ.get('access_token')
    refresh_token = os.environ.get('refresh_token')
    system_id = os.environ.get('system_id')
    rsp = submit_job(app_id, inputs, params, outputs, system_id,
                     access_token, refresh_token)


if __name__ == '__main__':
    main()