#
# Implements support for remote execution platforms such as agave.

import os
import requests
import time
import urlparse

# requests.packages.urllib3.disable_warnings()

from agavepy.agave import Agave, AgaveException
from agavepy.async import AgaveAsyncResponse
import jinja2

from .error import Error
from .config import Config
from .docker import RUNNING_IN_DOCKER, DOCKER_BASE
from .template import ConfigGen

JOB_TEMPLATE = 'job.j2'
EOD_TEMPLATE = 'eod.j2'
HERE = os.path.dirname(os.path.abspath((__file__)))


class AgaveExecutor(object):
    """Execute a task in the Agave cloud"""

    def __init__(self, wf_name, url=None, username=None, password=None,
                 client_name=None, client_key=None, client_secret=None,
                 storage_system=None, home_dir=None, verify=None, create_home_dir=True,
                 access_token=None, refresh_token=None, admin_password=None):
        self.from_config()
        if not url:
            url = self.api_server
        if not username:
            username = self.username
        if not password:
            password = self.password
        if not admin_password:
            admin_password = self.admin_password
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
        if verify is None:
            verify = self.verify
        print "Constructing executor for: ", url
        if access_token and refresh_token:
            print "Using access token: {}".format(access_token)
            self.ag = Agave(api_server=url, token=access_token, refresh_token=refresh_token,
                        client_name=client_name, api_key=client_key, api_secret=client_secret, verify=verify)
        else:
            print "Using username: {}".format(username)
            self.ag = Agave(api_server=url, username=username, password=password,
                        client_name=client_name, api_key=client_key, api_secret=client_secret,
                        verify=verify, admin_password=admin_password)
        print("executor constructed.")
        self.storage_system = storage_system
        print("Storage system: {}".format(storage_system))
        self.wf_name = wf_name
        self.home_dir = home_dir
        # default the home directory to the username
        if not self.home_dir:
            self.home_dir = '/home/' + username
        print("Home dir: {}".format(home_dir))
        # get the home dir for the system itself:
        rsp = self.ag.systems.get(systemId=storage_system)
        self.system_homedir = rsp.get('storage').get('homeDir')
        self.working_dir = os.path.join(self.home_dir, wf_name)
        print("Working directory for this eod run: {}".format(self.working_dir))
        # create the working directory now
        if create_home_dir:
            try:
                print("Creating the working directory on the storage system. Full path: {}".format(self.working_dir))
                rsp = self.ag.files.manage(systemId=self.storage_system,
                                           filePath=self.home_dir,
                                           body={'action':'mkdir',
                                                 'path':wf_name})
            except (requests.exceptions.HTTPError, AgaveException):
                # if the directory already exists we could get an error trying to create it.
                print("Error creating directory. Ignoring...")
                return
            print("Directory created.")

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
            self.username = os.environ.get('AGAVE_USERNAME')
        if not self.username:
            raise Error('Invalid config: username is required.')
        self.password = Config.get('agave', 'password')
        if not self.password:
            self.password = os.environ.get('AGAVE_PASSWORD')
        self.admin_password = Config.get('agave', 'admin_password')
        if not self.admin_password:
            self.admin_password = os.environ.get('AGAVE_ADMIN_PASSWORD')
        if not self.password and not self.admin_password:
            raise Error('Invalid config: password is required.')
        self.client_name = Config.get('agave', 'client_name')
        if not self.client_name:
            raise Error('Invalid config: client_name is required.')

        # optional args:
        self.verify = Config.get('agave', 'verify')
        if self.verify == 'False':
            self.verify = False
        if self.verify == 'True':
            self.verify = True
        self.client_key = Config.get('agave', 'client_key')
        self.client_secret = Config.get('agave', 'client_secret')
        if not self.client_secret:
            self.client_secret = os.environ.get('AGAVE_CLIENT_SECRET')
        self.storage_system = Config.get('agave', 'storage_system')
        if not self.storage_system:
            if 'agave.iplantc.org' in self.api_server:
                self.storage_system = 'data.iplantcollaborative.org'
            else:
                self.storage_system = 'endofday.local.storage.com'
        self.home_dir = Config.get('agave', 'home_dir')
        self.email = Config.get('agave', 'email')

    def create_dir(self, path):
        """Create a directory on the configured storage system inside the endofday home dir. The path argument
        should be a relative path; a leading slash will be removed.
        """
        if path.startswith('/'):
            path = path[1:]
        print "creating remote storage directory:", path, "..."
        try:
            rsp = self.ag.files.manage(systemId=self.storage_system,
                                       filePath=self.home_dir,
                                       body={'action':'mkdir',
                                             'path':path})
            print "directory created."
        except Exception as e:
            if 'already exists' in str(e.message):
                print("Directory already exists.")
                return True
            else:
                raise Error("Error creating directory on default storage system. Path: " + path + "Msg:" + str(e))
        return rsp

    def upload_file(self, local_path, remote_path):
        """Upload a file on the local system to remote storage. The remote_path param should
        be relative to the endofday home dir. The local_path should be absolute.
        """
        if remote_path.startswith('/'):
            remote_path = remote_path[1:]
        sourcefilePath = os.path.join(self.home_dir, remote_path)
        try:
            rsp = self.ag.files.importData(systemId=self.storage_system,
                                           filePath=sourcefilePath,
                                           fileToUpload=open(local_path,'rb'))
        except Exception as e:
            raise Error("Exception on file upload - local_path: " + local_path +
                        "; remote_path: " + remote_path + ' sourceFilePath: ' + sourcefilePath + "; e:" + str(e))
        # something went wrong
        if type(rsp) == dict:
            raise Error('Unexpected response on file upload - local_path: ' + local_path +
                        '; remote_path: ' + remote_path + ' sourceFilePath: ' + sourcefilePath + '. Response:' + str(rsp))
        return AgaveAsyncResponse(self.ag, rsp)

    def download_file(self, local_path, remote_path):
        """
        Download a file from remote storage to the local path. The remote_path param should be relative to the
        endofday home dir and the local_path should be absolute.
        """
        if remote_path.startswith('/'):
            remote_path = remote_path[1:]
        path = os.path.join(self.system_homedir, self.home_dir, remote_path)
        print "Downloading file from:", remote_path, " to:", local_path, "..."
        with open(local_path, 'wb') as f:
            rsp = self.ag.files.download(systemId=self.storage_system, filePath=path)
            if type(rsp) == dict:
                raise Error("Error downloading file at path: " + remote_path + ", filePath:"+ path+ ". Response: " + str(rsp))
            for block in rsp.iter_content(1024):
                if not block:
                    break
                f.write(block)
        print "Download successful."
        return {'status': 'success'}

    def create_volumes(self, task):
        """
        Create volume directories on the local host and in the remote storage system to store outputs of the
        container execution.
        """
        for dir in task.volume_dirs:
            if RUNNING_IN_DOCKER:
                path = dir.docker_host_path
            else:
                path = dir.host_path
            if not os.path.exists(path):
                print "locally creating: ", path
                os.makedirs(path)
        # create directories in the remote storage:
        for dir in task.volume_dirs:
            self.create_dir(path=dir.eod_rel_path)

    def upload_inputs(self, task):
        """
        Upload inputs needed for container execution.
        """
        responses = []
        for inpv in task.input_volumes:
            if RUNNING_IN_DOCKER:
                local_path = inpv.docker_host_path
            else:
                local_path = inpv.host_path
            remote_dir = inpv.eod_rel_path
            if not remote_dir[-1] == '/':
                remote_dir = os.path.split(remote_dir)[0]
            print "creating remote directory for input:", local_path, "remote dir path:", remote_dir
            self.create_dir(remote_dir)
            print "Uploading file", local_path, "to remote storage location:", inpv.eod_rel_path
            rsp = self.upload_file(local_path=local_path, remote_path=remote_dir)
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
        Generates an eod yaml file for running a single task in Agave cloud, and uploads the file to remote storage.
        Returns path of the file stored locally.
        :param task:
        :return:
        """
        context = self.get_task_context(task)
        conf = ConfigGen(EOD_TEMPLATE)
        env = jinja2.Environment(loader=jinja2.FileSystemLoader(HERE), trim_blocks=True, lstrip_blocks=True)
        # store yaml locally of the form <task.name>.yml
        if RUNNING_IN_DOCKER:
            path = os.path.join(task.docker_host_path, task.name + '.yml')
        else:
            path = os.path.join(task.base_path, task.name + '.yml')
        print "Generating eod file for task:", task.name, ' in:', path
        conf.generate_conf(context, path, env)
        return path

    def get_taskfile_context(self, taskfile):
        """
        Creates the context dictionary for generating an eod yaml file for running an entire workflow in Agave.
        :param task:
        :return:
        """
        context = {}
        context['wf_name'] = taskfile.name
        # create a global input for each input to the task
        context['global_inputs'] = []
        for gin in taskfile.global_inputs:
            inp = {'src': os.path.split(gin.src)[1], 'label': gin.label}
            context['global_inputs'].append(inp)
        # processes = [task for task in taskfile.tasks]
        processes = []
        for task in taskfile.tasks:
            process = {'name': task.name, 'image':task.image, 'command': task.command}
            process['inputs'] = []
            for inpv in task.inputs:
                inp = {'label': inpv.src, 'dest': inpv.dest}
                process['inputs'].append(inp)
            process['outputs'] = []
            for output in task.outputs:
                process['outputs'].append({'src':output.src, 'label': output.label})
            processes.append(process)
        context['processes'] = processes
        return context

    def get_taskfile(self, taskfile):
        """
        Generates an eod yaml file for running an entire eod workflow in the Agave cloud.
        :param taskfile:
        :return:
        """
        context = self.get_taskfile_context(taskfile)
        conf = ConfigGen(EOD_TEMPLATE)
        env = jinja2.Environment(loader=jinja2.FileSystemLoader(HERE), trim_blocks=True, lstrip_blocks=True)
        # store yaml locally in taskfile workdir:
        path = os.path.join(taskfile.work_dir, taskfile.name + '.yml')
        print "Generating eod file for taskfile:", taskfile.name, ' in:', path
        conf.generate_conf(context, path, env)
        return path

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

    def upload_task_defn(self, task):
        """
        Generate and upload the yml file representing this task.
        :param task:
        :return:
        """
        path = self.gen_task_defn(task)
        self.upload_file(local_path=path, remote_path=task.eod_rel_path)

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
            print "Job submitted successfully. URL:", rsp.url
            # block until job completes
            result = rsp.result()
            if not result == 'COMPLETE':
                raise Error("Job for task: " + task.name + " failed to complete. Job status: " + result + ". URL: " + rsp.url)
            print "Job completed."
            # download results:
            base_path = rsp.response.get('archivePath').strip(self.home_dir)
            print "Base archive path: ", base_path
            if base_path[0] == '/':
                base_path = base_path[1:]
            for output in task.outputs:
                local_path = os.path.join(task.base_path, output.src[1:])
                if RUNNING_IN_DOCKER:
                    local_path = os.path.join(task.docker_host_path, output.src[1:])
                # remote path is: <username>/<job-dir>/<wf_name>/<task_name>/<output>
                # base_path contains <username>/<job-dir>; wf_name == task_name
                remote_path = os.path.join(base_path, task.name, task.name, output.src[1:])
                try:
                    self.download_file(local_path=local_path, remote_path=remote_path)
                except Error as e:
                    print "Error downloading file. Job rsp: ", str(rsp), " Error: ", str(e)

        return action_fn

    def get_job(self, task):
        """
        Returns JSON description of an endofday job after compiling the job.j2 template.
        :param task:
        :return:
        """
        conf = ConfigGen(JOB_TEMPLATE)
        env = jinja2.Environment(loader=jinja2.FileSystemLoader(HERE), trim_blocks=True, lstrip_blocks=True)
        inputs = []
        input_base = 'agave://' + self.storage_system + '/' + self.system_homedir + '/'
        wf_path = input_base + os.path.join(self.home_dir, task.eod_rel_path, task.name + '.yml')
        for inpv in task.input_volumes:
            inp = {'path_str': input_base + os.path.join(self.home_dir, inpv.eod_rel_path) + ','}
            inputs.append(inp)
        # remove trailing comma from last entry:
        inputs[-1]['path_str'] = inputs[-1]['path_str'][:-1]
        context = {'wf_name': self.wf_name,
                   'task_name': task.name,
                   'global_inputs': inputs,
                   'wf_path': wf_path,
                   'system_id': self.storage_system}
        if self.email:
            context['email'] = self.email
        return conf.compile(context, env)

    def get_job_for_wf(self, taskfile, yaml_file_name):
        """
        Returns JSON description of an endofday job for entire wf after compiling the job.j2 template.
        :param task:
        :return:
        """
        conf = ConfigGen(JOB_TEMPLATE)
        env = jinja2.Environment(loader=jinja2.FileSystemLoader(HERE), trim_blocks=True, lstrip_blocks=True)
        inputs = []
        input_base = 'agave://' + self.storage_system + '/'
        wf_path = input_base + os.path.join(self.system_homedir + '/', self.home_dir, taskfile.name, yaml_file_name)
        for gin in taskfile.global_inputs:
            # URIs get passed 'as is' to Agave:
            if '://' in gin.src:
                path_str = gin.src
            else:
                path_str = input_base + os.path.join(self.system_homedir + '/',
                                                     self.home_dir,
                                                     taskfile.name,
                                                     'global_inputs', os.path.split(gin.src)[1])
            inp = {'path_str': path_str}
            inputs.append(inp)
        context = {'wf_name': self.wf_name,
                   'global_inputs': inputs,
                   'wf_path': wf_path,
                   'system_id': self.storage_system}
        if self.email:
            context['email'] = self.email
        return conf.compile(context, env)


    def submit_job(self, task):
        """
        Submits an Agave job to execute an endofday step in the cloud.
        :return:
        """
        job = self.get_job(task)
        print "Submitting job: ", str(job)
        try:
            rsp = self.ag.jobs.submit(body=job)
        except Exception as e:
            raise Error("Exception trying to submit job for task: " + task.name + ' job: ' + str(job) + '. Exception: ' + str(e))
        if type(rsp) == dict:
            raise Error("Error trying to submit job for task: " + task.name + ' job: ' + str(job) + '. Response: ' + str(rsp))
        return AgaveAsyncResponse(self.ag, rsp)


class AgaveAppExecutor(AgaveExecutor):
    """Executor to use to submit Agave jobs to run specific apps."""

    def get_action(self, task):
        return task.local_action_fn