#
# Implements support for remote execution platforms such as agave.

import os
import requests
import time

from agavepy.agave import Agave
import jinja2

from .error import Error
from .config import Config
from .template import ConfigGen

JOB_TEMPLATE = 'job.j2'
EOD_TEMPLATE = 'eod.j2'

class TimeoutError(Error):
    pass

class AgaveAsyncResponse(object):
    """
    Implements parts of the concurrent.futures.Future interface for nonblocking Agave responses.
    """
    def __init__(self, ag, response):
        """Construct an asynchronous response object from an Agave response which should be an agavepy.agave.AttrDict
        """
        self.ag = ag
        self.status = response.status
        self.retries = 0
        self.url = response._links.get('history').get('href')
        if not self.url:
            raise Error("Error parsing response object: no URL detected. response: " + str(response))
        # url's returned by agave sometimes have the version as 2.0, so we replace that here
        self.url = self.url.replace('/2.0/','/v2/')

    def _update_status(self):
        headers = {'Authorization': 'Bearer ' + self.ag.token.token_info.get('access_token')}
        rsp = requests.get(url=self.url, headers=headers)
        if (rsp.status_code == 404 or rsp.status_code == 403) and self.retries < 10:
            time.sleep(1.5)
            self.retries += 1
            return self._update_status()
        if not rsp.status_code == 200:
            raise Error("Error updating status; invalid status code:  " + str(rsp.status_code) + str(rsp.content))
        result = rsp.json().get('result')
        if not result:
            raise Error("Error updating status: " + str(rsp))
        # if the transfer ever completed, we'll call it good:
        if len([x for x in result if 'COMPLETE' in x['status']]) > 0:
            self.status = 'COMPLETE'
        # jobs end in 'finished' status
        elif len([x for x in result if 'FINISHED' in x['status']]) > 0:
            self.status = 'COMPLETE'
        else:
            # sort on creation time of the history object
            result = sorted(result, key=lambda k: k['created'])
            self.status = result[0].get('status')

    def _is_done(self):
        return self.status == 'COMPLETE' or self.status == 'STAGING_FAILED'

    def done(self):
        """Return True if the call was successfully cancelled or finished running."""
        self._update_status()
        return self._is_done()

    def result(self, timeout=None):
        """
        Returns the result of the original call, blocking until the result is returned or the timeout parameter is
        reached. The timeout paramter is interpreted in seconds.
        :param timeout:
        :return:
        """
        if self._is_done():
            return self.status
        self._update_status()
        now = time.time()
        if timeout:
            future = now + timeout
        else:
            future = float("inf")
        while time.time() < future:
            time.sleep(1)
            self._update_status()
            if self._is_done():
                return self.status
        raise TimeoutError()


class AgaveExecutor(object):
    """Execute a task in the Agave cloud"""

    def __init__(self, wf_name, url=None, username=None, password=None,
                 client_name=None, client_key=None, client_secret=None,
                 storage_system=None, home_dir=None):
        self.from_config()
        if not url:
            url = self.api_server
        if not username:
            username = self.username
        if not password:
            password = self.password
        if not client_name:
            client_name = self.client_name
        if not client_key:
            client_key = self.client_key
        if not client_secret:
            client_secret = self.client_secret
        if not storage_system:
            storage_system = self.storage_system
        if not home_dir:
            home_dir = self.home_dir
        self.ag = Agave(api_server=url, username=username, password=password,
                        client_name=client_name, api_key=client_key, api_secret=client_secret)
        self.storage_system = storage_system
        self.wf_name = wf_name
        self.home_dir = home_dir
        # default the home directory to the username
        if not self.home_dir:
            self.home_dir = username
        self.working_dir = os.path.join(self.home_dir, wf_name)
        # create the working directory now
        rsp = self.ag.files.manage(systemId=self.storage_system,
                                   filePath=self.home_dir,
                                   body={'action':'mkdir',
                                         'path':wf_name})

    def from_config(self):
        """
        Parses config file and updates instance.
        :return:
        """
        # required args
        self.api_server = Config.get('agave', 'api_server')
        if not self.api_server:
            raise Error('Invalid config: api_server is required.')
        self.username = Config.get('agave', 'username')
        if not self.username:
            raise Error('Invalid config: username is required.')
        self.password = Config.get('agave', 'password')
        if not self.password:
            self.password = os.environ.get('AGAVE_PASSWORD')
        if not self.password:
            raise Error('Invalid config: password is required.')
        self.client_name = Config.get('agave', 'client_name')
        if not self.client_name:
            raise Error('Invalid config: client_name is required.')

        # optional args:
        self.client_key = Config.get('agave', 'client_key')
        self.client_secret = Config.get('agave', 'client_secret')
        if not self.client_secret:
            self.client_secret = os.environ.get('AGAVE_CLIENT_SECRET')
        self.storage_system = Config.get('agave', 'storage_system')
        if not self.storage_system:
            self.storage_system = 'data.iplantcollaborative.org'
        self.home_dir = Config.get('agave', 'home_dir')

    def create_dir(self, path):
        """Create a directory on the configured storage system inside the endofday working
        directory. The path argument should be a relative path; a leading slash will be removed.
        """
        if path.startswith('/'):
            path = path[1:]
        print "creating remote storage directory:", path, "..."
        try:
            rsp = self.ag.files.manage(systemId=self.storage_system,
                                       filePath=self.working_dir,
                                       body={'action':'mkdir',
                                             'path':path})
        except Exception as e:
            raise Error("Error creating directory on default storage system. Path: " + path +
                        "Msg:" + str(e))
        print "directory created."
        return rsp

    def upload_file(self, local_path, remote_path):
        """Upload a file on the local system to remote storage. The remote_path param should
        be relative to the endofday working dir. The local_path should be absolute.
        """
        if remote_path.startswith('/'):
            remote_path = remote_path[1:]
        sourcefilePath = os.path.join(self.working_dir, remote_path)
        try:
            rsp = self.ag.files.importData(systemId=self.storage_system,
                                           filePath=sourcefilePath,
                                           fileToUpload=open(local_path,'rb'))
        except Exception as e:
            raise Error("Upload to default storage failed - local_path: " + local_path +
                        "; remote_path: " + remote_path + "; Msg:" + str(e))
        return AgaveAsyncResponse(self.ag, rsp)

    def download_file(self, local_path, remote_path):
        """
        Download a file from remote storage to the local path. The remote_path param should be relative to the
        endofday working dir and the local_path should be absolute.
        """
        if remote_path.startswith('/'):
            remote_path = remote_path[1:]
        path = os.path.join(self.working_dir, remote_path)
        with open(local_path, 'wb') as f:
            rsp = self.ag.files.download(systemId=self.storage_system, filePath=path)
            for block in rsp.iter_content(1024):
                if not block:
                    break
                f.write(block)
        return {'status': 'success'}

    def create_volumes(self, task):
        """
        Create volume directories in the remote storage system to store outputs of the container execution.
        """
        for dir in task.volume_dirs:
            path = dir.eod_rel_path.strip(self.wf_name)
            self.create_dir(path=path)

    def upload_inputs(self, task):
        """
        Upload inputs needed for container execution.
        """
        responses = []
        for inpv in task.input_volumes:
            remote_path = inpv.eod_rel_path.strip(self.wf_name)
            print "Uploading file", inpv.host_path, "to remote storage location:", remote_path
            rsp = self.upload_file(local_path=inpv.host_path, remote_path=remote_path)
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

    def get_task_context(self, task):
        """
        Creates the context dictionary for generating an eod yaml file for running a single task on Agave cloud.
        :param task:
        :return:
        """
        context = {}
        context['wf_name'] = task.name
        # create a global input for each input to the task
        context['global_inputs'] = []
        for idx, inpv in enumerate(task.input_volumes):
            src = os.path.split(inpv.host_path)
            if len(src) > 1:
                src = src[1]
            else:
                src = src[0]
            inp = {'src': src, 'label': 'input_' + str(idx)}
            context['global_inputs'].append(inp)
        process = {'name': task.name, 'image':task.image, 'command': task.command}
        process['inputs'] = []
        for idx, inpv in enumerate(task.input_volumes):
            inp = {'label':'inputs.input_' + str(idx), 'dest': inpv.container_path}
            process['inputs'].append(inp)
        process['outputs'] = []
        for output in task.outputs:
            process['outputs'].append({'src':output.src, 'label': output.label})
        context['processes'] = [process]
        return context

    def gen_task_defn(self, task):
        """
        Generates an eod yaml file for running a single task on Agave cloud, and uploads the file to remote storage.
        :param task:
        :return:
        """
        context = self.get_task_context(task)


    def get_docker_cmd(self, task):
        """
        Returns the docker command needed to execute an endofday container in the Agave cloud.
        :return:
        """
        cmd = 'docker run --rm eod-jobs-submit -W -z ' + self.ag.token.token_info.get('access_token')
        # order important -- mount output volumes first so that inputs overlay them
        for volume in task.volume_dirs:
            cmd += ' -m ' + volume.eod_rel_path + ':' + volume.container_path
        for volume in task.input_volumes:
            cmd += ' -n ' + volume.eod_rel_path + ':' + volume.container_path
        cmd += ' -I ' + task.image
        cmd += ' -c ' + task.command
        return cmd

    def get_action(self, task):
        """
        Returns a callable for executing a task in the Agave cloud.
        """

        def action_fn():
            """
            This function does the following things:
            1. Create directories on the storage system for the output volumes.
            2. Upload all inputs needed for the task to the default storage.
            3. Submit a job to actually execute the docker container, staging inputs and archiving outputs.
            4. Download outputs from storage to the local system once job completes.
            :return:
            """
            self.create_volumes(task)
            self.upload_inputs(task)
            self.upload_task_defn(task)
            rsp = self.submit_job(task)
            # block until job completes
            result = rsp.result()
            if not result == 'COMPLETE':
                raise Error("Job for task: " + task.name + " failed to complete. Job status: " + result + ". URL: " + rsp.url)
            # download results:


        return action_fn

    def get_job(self, task):
        """
        Returns JSON description of an endofday job after compiling the job.j2 template.
        :param task:
        :return:
        """
        conf = ConfigGen(JOB_TEMPLATE)
        env = jinja2.Environment(loader=jinja2.FileSystemLoader(os.getcwd()), trim_blocks=True, lstrip_blocks=True)
        inputs = []
        input_base = 'agave://' + self.storage_system + '//'
        for inpv in task.input_volumes:
            inp = {'path_str': input_base + os.path.join(self.working_dir, inpv.eod_rel_path.strip(self.wf_name)[1:]) + ','}
            inputs.append(inp)
        # remove trailing comma from last entry:
        inputs[-1]['path_str'] = inputs[-1]['path_str'][:-1]
        context = {'wf_name': self.wf_name,
                   'task_name': task.name,
                   'global_inputs': inputs,}
        return conf.compile(context, env)

    def submit_job(self, task):
        """
        Submits an Agave job to execute an endofday step in the cloud.
        :return:
        """
        job = self.get_job(task)
        try:
            rsp = self.ag.jobs.submit(body=job)
        except Exception as e:
            raise Error("Error trying to submit job for task: " + task.name + '. Exception: ' + str(e))
        return AgaveAsyncResponse(self.ag, rsp)
