# Execute an entire endofday workflow in the Agave cloud.


import argparse
import os
import requests

from .docker import RUNNING_IN_DOCKER
from .error import Error
from .executors import AgaveExecutor, AgaveAsyncResponse
import tasks


def upload_inputs(task_file):
    # make directory for global inputs on remote storage:
    ginp_dir = os.path.join(task_file.name, 'global_inputs')
    task_file.ae.create_dir(path=ginp_dir)
    responses = []
    inp_names = [os.path.split(inp.src) for inp in task_file.global_inputs]
    if not len(inp_names) == len(set(inp_names)):
        raise Error("For remote executions, the global inputs must have unique names.")
    for inp in task_file.global_inputs:
        if inp.src.startswith('agave://'):
            continue
        local_path = inp.host_path
        if RUNNING_IN_DOCKER:
            local_path = inp.docker_host_path
        print "Uploading file", local_path, "to remote storage location:", ginp_dir
        rsp = task_file.ae.upload_file(local_path=local_path, remote_path=ginp_dir)
        responses.append(rsp)
    # block until transfers complete
    for rsp in responses:
        print "Waiting on upload:", rsp.url
        status = rsp.result()
        if status == 'COMPLETE':
            print "Upload completed."
        else:
            print "Upload failed... aborting."
            raise Error("There was an error uploading a file to remote storage. Status:" + status
                        + ". URL: " + rsp.url)

def upload_yml(tasl_file):
    path = tasl_file.ae.get_taskfile(tasl_file)
    # upload to the base directory for the wf:
    tasl_file.ae.upload_file(local_path=path, remote_path=tasl_file.name)

def submit_job(task_file):
    job = task_file.ae.get_job_for_wf(task_file)
    print "Submitting job: ", str(job)
    try:
        rsp = task_file.ae.ag.jobs.submit(body=job)
    except Exception as e:
        raise Error('Exception trying to submit job: ' + str(job) + '. Exception: ' + str(e))
    if type(rsp) == dict:
        raise Error('Error trying to submit job: ' + str(job) + '. Response: ' + str(rsp))
    return AgaveAsyncResponse(task_file.ae.ag, rsp)


def main(yaml_file):
    task_file = tasks.TaskFile(yaml_file)
    if not hasattr(task_file, 'ae'):
        task_file.ae = AgaveExecutor(wf_name=task_file.name)
    task_file.create_glob_ins()
    task_file.create_tasks()
    upload_inputs(task_file)
    upload_yml(task_file)
    rsp = submit_job(task_file)
    print "Response:", str(rsp)

if __name__ == '__main__':
    requests.packages.urllib3.disable_warnings()
    parser = argparse.ArgumentParser(description='Execute eod workflow in the Agave cloud.')
    parser.add_argument('yaml_file', type=str,
                        help='Yaml file to parse')
    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true')
    parser.set_defaults(verbose=False)
    args = parser.parse_args()
    main(args.yaml_file)