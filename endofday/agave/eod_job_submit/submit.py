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

sys.path.append('/')

import jinja2

from agavepy.agave import Agave
from core.template import ConfigGen
from core.error import Error
from core.executors import AgaveAsyncResponse


HERE = os.path.dirname(os.path.abspath((__file__)))

JOB_TEMPLATE = '/job.j2'

VERIFY = False

def get_inputs():
    """Returns a list of dictionaries of the form
    [ { 'id': <input_id>, 'uris': [<uri_1>, ...,<uri_n>] }]. """
    # immediate subdirectories are the input ids
    input_ids = [y for y in os.listdir('/agave/inputs') if os.path.isdir(os.path.join('/agave/inputs', y))]
    inputs = []
    for input_id in input_ids:
        uris = []
        for name in os.listdir(os.path.join('/agave/inputs/',input_id)):
            with open(os.path.join('/agave/inputs/',input_id, name), 'r') as f:
                uri = f.readline().strip('\n')
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
        job_path_or_id = f.readline().strip('\n')
        outputs.append(job_path_or_id)
    return outputs

def quote(elm):
    """Custom jinja2 filter to properly quote an element of a JSON document."""
    try:
        int(elm)
    except (TypeError, ValueError):
        if isinstance(elm, str):
            if elm.lower() == 'true' or elm.lower() == 'false':
                return elm.lower()
            return '"{}"'.format(elm)
    return elm

def submit_job(app_id, inputs, params, outputs, system_id,
               access_token, refresh_token, api_server, api_key, api_secret, verify):
    parameters = []
    for k,v in params.items():
        parm = {'id':k, 'value': v}
        parameters.append(parm)
    print("parameters: {}".format(parameters))
    context = {'app_id': app_id,
               'system_id': system_id,
               'inputs': inputs,
               'parameters': parameters,
               }
    conf = ConfigGen(JOB_TEMPLATE)
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(HERE), trim_blocks=True, lstrip_blocks=True)
    env.filters['quote'] = quote
    job = conf.compile(context, env)

    ag = Agave(api_server=api_server,
               api_key=api_key,
               api_secret=api_secret,
               token=access_token,
               refresh_token=refresh_token,
               verify=verify)
    print("Submitting job: {}".format(job))
    try:
        rsp = ag.jobs.submit(body=job)
    except Exception as e:
        raise Error("Got an exception trying to submit the job: {}".format(e))
    job_id = rsp.get('id')
    print("Job submitted. job_id:{}".format(job_id))
    return AgaveAsyncResponse(ag, rsp), job_id

def to_uri(output, job_id, api_server):
    """Convert an output of a job to an agave URI."""
    # todo - for the first release, we only support relative paths in the job's work dir
    # to the output. In the future, we can support an output_id which we can convert to a path
    # using the app's description
    return '{}/jobs/v2/{}/outputs/media/{}'.format(api_server, job_id, output)

def write_outputs(outputs, job_id, api_server):
    """Create files representing outputs of the job with the URIs as contents."""
    for output in outputs:
        path = os.path.join('/agave/outputs/', output)
        base_dir = os.path.dirname(path)
        if not os.path.exists(base_dir):
            print("Creating base dir for output: {}".format(base_dir))
            os.makedirs(base_dir)
        with open(path, 'w') as f:
            print("Writing output file to path: {}".format(path))
            print(to_uri(output, job_id, api_server), file=f)

def main():
    args = dict([arg.split('=', 1) for arg in sys.argv[1:]])
    app_id = args.pop('app_id', None)
    if not app_id:
        raise Error("app_id is required.")
    print("eod_job_submit executing for app: {}".format(app_id))
    params = args
    print("Parameters:{}".format(params))

    inputs = get_inputs()
    print("Inputs:{}".format(inputs))

    outputs = get_outputs()
    print("Outputs:{}".format(outputs))

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

    system_id = os.environ.get('system_id')
    if not system_id:
        raise Error("system_id is required.")
    print("eod_job_submit executing for system: {}".format(system_id))
    rsp, job_id = submit_job(app_id, inputs, params, outputs, system_id,
                     access_token, refresh_token, api_server, api_key, api_secret, verify)
    # block until job completes
    print("Async response object from submit: {}".format(rsp.response))
    result = rsp.result()
    if not result == 'COMPLETE':
        raise Error("Job for app_id: " + app_id + " failed to complete. Job status: " + result + ". URL: " + rsp.url)
    print("Job completed.")
    write_outputs(outputs, job_id, api_server)
    print("Outputs written:{}".format(outputs))


if __name__ == '__main__':
    main()