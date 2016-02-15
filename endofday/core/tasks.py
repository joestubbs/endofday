from __future__ import print_function

import argparse
import multiprocessing
import os
import pipes
import subprocess
import sys

from collections import OrderedDict
import requests
import rfc3987
import yaml

from doit.task import dict_to_task
from doit.cmd_base import TaskLoader
from doit.doit_cmd import DoitMain

from .config import Config
from .error import Error
from .executors import AgaveAsyncResponse, AgaveExecutor, AgaveAppExecutor
from .hosts import update_hosts


# Current working directory of the host, passed in as an environmental variable by the alias.sh
HOST_BASE = os.environ.get('STAGING_DIR')

# the directory in the eod container that contains the current working directory of the host
EOD_CONTAINER_BASE = '/staging'

# whether or not the execution is running in the Agave cloud. This environmental variable is set by the
# eod wrapper.sh script and prevents resubmitting individual tasks (or other sub-workflows) to Agave after an initial
# submission.
RUNNING_IN_AGAVE = os.environ.get('RUNNING_IN_AGAVE', False)
print ("Running in Agave cloud: {}".format(RUNNING_IN_AGAVE))

ADMIN_PASS = os.environ.get('ADMIN_PASS', 'n/a')

def to_eod(host_path):
    """Convert an absolute path on the host to an absolute path in the eod container"""
    if host_path.startswith(HOST_BASE):
        return host_path.replace(HOST_BASE, EOD_CONTAINER_BASE)
    else:
        return os.path.join('/host', host_path[1:])

def get_host_work_dir(wf_name):
    """Return the working directory in the host for a work file"""
    return os.path.join(HOST_BASE, wf_name)

# the directory where the eod_submit_job container will look for inputs'
AGAVE_INPUTS_DIR = '/agave/inputs'

# the directory where the eod_submit_job container will look for inputs'
AGAVE_OUTPUTS_DIR = '/agave/outputs'


# global tasks list to pass to the DockerLoader
tasks = []

verbose = False

class GlobalInput(object):
    """
    Represents an input to a workflow. E.g. for a string input <- /data/foo/input.txt
    src =  /data/foo/input.txt
    label = input

    Could also be:
    input <- workflow1.output (and then we need to resolve this)

    """

    def __init__(self, label, src, wf_name):
        # a label to reference this input by in other parts of the wf file.
        self.label = label

        # src can either be:
        # 1) URI
        # 2) absolute path on the host
        # 3) relative path on the host, relative to the CWD of eod
        # In the FUTURE: should also allow
        # 4) a global output of another eod.yml, in which case it should be <wf_name>.<outputs>.<label>
        # (this is not yet supported)

        self.src = src

        self.is_uri = False
        if rfc3987.match(self.src, 'URI'):
            self.is_uri = True
            self.uri = self.src

        self.set_abs_host_path(wf_name)
        if not self.abs_host_path:
            raise Error("Could not compute host path for src:{}, label:{}".format(src, label))
        self.eod_container_path = to_eod(self.abs_host_path)
        base_dir = os.path.dirname(self.eod_container_path)
        # make sure the parent directory exists,
        if not os.path.exists(base_dir):
            print("Creating global input base_dir:{}".format(base_dir))
            os.makedirs(base_dir)
        # create a file with the URI
        if self.is_uri:
            with open(self.eod_container_path, 'w') as f:
                print(self.uri, file=f)

    def __str__(self):
        return 'GlobalInput:' + self.label

    def __ref__(self):
        return 'GlobalInput:' + self.label

    def set_abs_host_path(self, wf_name):
        """Compute the absolute host path for this global input."""
        if self.is_uri:
            self.abs_host_path = os.path.join(get_host_work_dir(wf_name),
                                              'global_inputs',
                                              self.label)
        else:
            if self.src.startswith('/'):
                self.abs_host_path = self.src
            # otherwise, it's a relative path so it will be in the HOST_BASE
            else:
                self.abs_host_path = os.path.join(HOST_BASE, self.src)

    def set_used_locally(self, tasks):
        """Determine whether this global input is used by a local task. Can only be run once all tasks are created."""
        self.used_locally = set_used_locally(self, tasks)

def set_used_locally(obj, tasks):
    """Determine whether a GlobalInput or TaskOutput is used by a local task. obj should be the GlobalInput or
    TaskOutput.
    """
    if isinstance(obj, GlobalInput):
        cls = GlobalInput
    else:
        cls = TaskOutput
    used_locally = False
    for task in tasks:
        # ignore remote tasks
        if not task.execution == 'docker':
            continue
        for inp in task.inputs:
            # if the src task has the same parent with the same label, we have a match
            if isinstance(inp.real_source, cls) and inp.real_source.label == obj.label:
                used_locally = True
                break
    return used_locally

class Volume(object):
    """
    Represents a volume mounted into a container for a task.
    """
    def __init__(self, host_path, container_path):
        self.host_path = host_path
        self.container_path = container_path

    def to_str(self):
        """ Return a string that can be used in a docker command. """
        return '-v {}:{} '.format(self.host_path, self.container_path)


def resolve_source(src, global_inputs, tasks):
    """ Returns a GlobalInput or a TaskOutput object matching the label in 'src'.
    """
    src_task = src.split('.')[0]
    src_name = src.split('.')[1]
    if src_task == 'inputs':
        # src references a global input, so look through global_inputs
        sources = global_inputs
    else:
        # src references another task output
        for task in tasks:
            if task.name == src_task:
                sources = task.outputs
                break
        else:
            # didn't find the task label
            raise Error("Input reference to task not found. src:{}, src_task:{}, src_name:{}, Sources:{}".format(src, src_task, src_name, tasks))
    for source in sources:
        if source.label == src_name:
            return source
    else: # this is on for loop: if we did not break, we did not find the input
        sources_str = ''
        for source in sources:
            sources_str += source.label + ', '
        raise Error("Input reference not found. src:{}, src_task:{}, src_name:{}, Sources:{}".format(src, src_task, src_name, sources_str))


class TaskInput(object):
    """
    Represents a file input to a task within a workflow.
    """
    def __init__(self, src, dest):
        # src is a reference to either a global input or an output of another task.
        self.src = src

        if not len(src.split('.')) == 2:
            raise Error('Invalid source for task resource: ' + str(src)
                        + ' format is: <task>.<name>')
        # the task name should either be 'inputs' to refer to a global input
        # or it should be the name of another task.
        self.src_task = self.src.split('.')[0]
        self.src_name = self.src.split('.')[1]

        # dest is a container path
        self.dest = dest

        # real_source is either a GlobalInput object or a TaskOutput object. It is
        # computed later, once all tasks have been created.
        self.real_source = None

    def set_real_source(self, global_inputs, tasks):
        """Resolves the src to a global input or task output."""
        self.real_source = resolve_source(self.src, global_inputs, tasks)

    def set_volume(self, global_inputs, tasks, simple_task):
        self.volume = Volume(self.real_source.abs_host_path, self.dest)


class AddedInput(object):
    """TaskInput-like object that can be added to a task's inputs list by the eod engine. Because it
    implements the get_volume method, this input behaves just like a TaskInput created from the user's
    yaml file.
    """

    def __init__(self, host_path, container_path):
        self.host_path = host_path
        self.container_path = container_path
        self.abs_host_path = host_path
        # in this case, the real_source is this input so reference it directly.
        self.real_source = self

    def set_volume(self, global_inputs, tasks, simple_task):
        self.volume = Volume(self.host_path, self.container_path)

    def set_real_source(self, global_inputs, tasks):
        """Resolves the src to a global input or task output."""
        # in this case, the real source is the added input and is set in the constructor.
        pass

class TaskOutput(object):
    """
    Represents a file output of a task within a workflow.
    """
    def __init__(self, src, label, wf_name, task_name, is_uri=False):
        # src is an absolute path in a container
        self.src = src
        if not self.src.startswith('/'):
            raise Error("Invalid output format - container paths must be absolute.")

        # the actual name of the file
        self.file_name = os.path.split(self.src)[1]

        # label is how this output will be referenced in other parts of the yml file
        self.label = label

        # the wf that this task belongs to
        self.wf_name = wf_name

        # the task that this output belongs to
        self.task_name = task_name

        # abs path on the host where this output can be found
        self.abs_host_path = self.get_abs_host_path()

        # if the local file merely points to a remote file via a URI (e.g. an AgaveAppTaskOutput). In this case, set a
        # path location on the host for caching the file, if necessary.
        self.is_uri = is_uri

        # immediate directory on the host containing this output
        self.host_directory = os.path.split(self.abs_host_path)[0]

        # abs path in the eod container where this output can be found
        self.eod_container_path = self.get_eod_container_path()

        # immediate directory in the eod container containing this output
        self.eod_directory = os.path.split(self.eod_container_path)[0]

        self.volume = self.get_volume()

    def get_abs_host_path(self):
        """ Returns an absolute path on the host to this output file. """
        return os.path.join(HOST_BASE, self.wf_name, self.task_name, self.src[1:])

    def get_eod_container_path(self):
        """ Returns an absolute path in the eod container to this output file. """
        return to_eod(self.abs_host_path)

    def set_used_locally(self, tasks):
        """Determine whether this output is used by a local task. Can only be run once all tasks are created."""
        self.used_locally = set_used_locally(self, tasks)

    def get_volume(self):
        """ Create a volume object for this task output."""

        return Volume(host_path=self.host_directory,
                      container_path=os.path.split(self.src)[0])


class AgaveAppTaskInput(object):
    """
    Represents an input to a task which is of execution type 'agave_app'
    """
    def __init__(self, input_id, source_desc, idx):
        # The Agave app input id for this input
        self.input_id = input_id

        # a source (label), which refers to either a global input or a task output.
        self.source_desc = source_desc

        # the index of this input for the input_id
        self.idx = idx

        # create a task input for the eod_submit_job container
        self.task_input = TaskInput(src=source_desc,
                                    dest=os.path.join(AGAVE_INPUTS_DIR,
                                                      input_id,
                                                      str(idx)))


class AgaveAppTaskOutput(object):
    """
    Represents an output of a task which is of execution type 'agave_app'
    """
    def __init__(self, src, label, wf_name, task_name):
        # src is till tbd -- probably an Agave app output id or name
        self.src = src

        # label is how this output will be referenced in other parts of the yml file
        self.label = label

        # the wf that this task belongs to
        self.wf_name = wf_name

        # the task that this output belongs to
        self.task_name = task_name

        # create a task output for the eod_submit_job container. Note: all AgaveAppTasksOutputs
        # correspond to remote files, so is_uri should be true.
        self.task_output = TaskOutput(src=os.path.join(AGAVE_OUTPUTS_DIR, self.src),
                                      label=self.label,
                                      wf_name=self.wf_name,
                                      task_name=self.task_name,
                                      is_uri=True)

class BaseDockerTask(object):
    """ Base class for all pydoit tasks.
    """
    def __init__(self, name, desc, wf_name):
        # name of the task
        self.name = name

        # name of the wf this task belongs to
        self.wf_name = wf_name

        # user supplied description of the task
        self.description = desc.get('description')

        # inputs description
        self.inputs_desc = desc.get('inputs') or []

        # outputs description
        self.outputs_desc = desc.get('outputs') or []

        # whether to run locally or in the Agave cloud
        # supported execution types are: 'docker', 'agave', and 'agave_app'
        self.execution = desc.get('execution', 'docker')
        if self.execution == 'agave':
            # check to see if we are already executing on the agave cloud and if so, ignore this option:
            if RUNNING_IN_AGAVE:
                self.execution = 'docker'

        # Input objects list
        self.inputs = []

        # Output objects list
        self.outputs = []

        # Outputs to mount
        self.output_volume_mounts = []

        # base path for this task, relative to the eod container, for this task
        self.eod_base_path = os.path.join(EOD_CONTAINER_BASE, wf_name, self.name)

        # Create the base path if it doesn't exist
        if not os.path.exists(self.eod_base_path):
            print("Creating task base_dir:{}".format(self.eod_base_path))
            os.makedirs(self.eod_base_path)

    def parse_in_out_desc(self, desc, kind):
        """ Parses the inputs/outputs description and returns a list of pairs, (src, dest).

        kind should be either 'input' or 'output'
        """
        result = []
        for obj in desc:
            if not len(obj.split('->')) == 2:
                raise Error("Invalid {} format in {} process: {} ".format(kind, self.name, obj) +
                            " Format should be: <source> -> <destination>")
            src, dest = obj.split('->')
            result.append((src.strip(), dest.strip()))
        return result

    def set_output_volume_mounts(self):
        """
        We create directories on the host and mount them into the container at
        run time so that we have access to the outputs. Each volume consists of
        two paths: the path on the host and the path in the container. For each
        output, we create a volume to mount that is the immediate parent
        directory containing the core unless it is a directory in which case
        we mount the directory itself. Note also that we may not need to mount
        anything if another output would mount the same or larger directory.
        """
        result = []
        output_volumes = []
        for output in self.outputs:
            output_volumes.append(output.volume)
        output_volumes.sort(key= lambda vol:vol.container_path)
        # add volumes from dirs_list, removing extraneous ones
        for volume in output_volumes:
            head, tail = os.path.split(volume.container_path)
            while head and tail:
                if head in [volume.container_path for volume in result]:
                    break
                head, tail = os.path.split(head)
            else:
                result.append(volume)
        self.output_volume_mounts = result

    def get_docker_command(self, envs=None):
        """
        Returns a docker run command for executing the task image.
        """
        docker_cmd = "docker run --rm"
        # order important here -- need to mount output dirs first so that
        # inputs overlay them.
        output_str = ' '
        for volume in self.output_volume_mounts:
            output_str += volume.to_str()
        docker_cmd += output_str
        input_str = ''
        for inp in self.inputs:
            input_str += inp.volume.to_str()
        docker_cmd += input_str
        if envs:
            for k,v in envs.items():
                docker_cmd += ' -e ' + '"' + str(k) + '=' + str(v) + '"'
        # add the image:
        docker_cmd += self.image + ' '
        # add the command:
        docker_cmd += self.command
        return docker_cmd, output_str, input_str

    def local_action_fn(self):
        """
        Execute the docker container on the local machine.
        """
        self.pre_action()
        docker_cmd, _, _ = self.get_docker_command(envs=getattr(self, 'envs', None))
        # now, execute the container
        print("Executing docker command:{}".format(docker_cmd))
        proc = subprocess.Popen(docker_cmd, shell=True)
        proc.wait()
        self.post_action()

    def set_action(self, executor=None):
        """
        The action for a task is the function that is actually called by
        pydoit to execute the task.
        """

        # if the task instance has its own executor, use that:
        if hasattr(self, 'executor'):
            self.action = self.executor.get_action(self)
        # otherwise, if we were passed a (global) executor, use that:
        elif executor:
            self.action = executor.get_action(self)
        # otherwise, use the local action
        else:
            self.action = self.local_action_fn

    def pre_action(self):
        """Subclasses can override this method to do any task pre-processing before the
        docker container is executed."""
        pass

    def post_action(self):
        """Subclasses can override this method to do any task post-processing after the
        docker container execution completes."""
        pass

    def set_doit_dict(self):
        """
        Sets the dictionary that can be used to generate a doit task.
        """
        # the file dependencies for this task whose paths need to refer to the eod container
        file_deps = []
        for inp in self.inputs:
            file_deps.append(to_eod(inp.real_source.abs_host_path))

        # the files generated by this task whose paths also need to refer to the eod container
        targets = []
        for output in self.outputs:
            targets.append(to_eod(output.abs_host_path))

        self.doit_dict = {
            'name': self.name,
            'actions': [self.action],
            'doc': self.description,
            'targets': targets,
            'file_dep': file_deps,
        }

    def set_input_volumes(self, global_inputs, tasks):
        """ Set the input volumes for this task, once all tasks have been created."""
        result = []
        for inp in self.inputs:
            inp.set_volume(global_inputs, tasks, simple_task=isinstance(self, SimpleDockerTask))
            result.append(inp.volume)
        self.input_volumes = result


class SimpleDockerTask(BaseDockerTask):
    """ Represents a task that executes a docker container.
    """
    def __init__(self, name, desc, wf_name):
        super(SimpleDockerTask, self).__init__(name, desc, wf_name)

        # docker image to use
        self.image = desc.get('image')

        # command to run within the docker container
        self.command = desc.get('command')

        self.audit()

        # create the TaskInput objects
        for inp in self.parse_in_out_desc(self.inputs_desc, 'input'):
            self.inputs.append(TaskInput(src=inp[0], dest=inp[1]))

        # create the TaskOutput objects
        for out in self.parse_in_out_desc(self.outputs_desc, 'output'):
            self.outputs.append(TaskOutput(src=out[0],
                                           label=out[1],
                                           wf_name=wf_name,
                                           task_name=self.name))

    def audit(self):
        """Run basic audits on a constructed task. Work in progress."""
        if not self.name:
            raise Error("Name required for every task.")
        if not type(self.name) == str:
            raise Error("Name must be a string.")
        self.name = self.name.strip()
        if not self.image:
            raise Error("No image specified for task: " + self.name)
        if not type(self.image) == str:
            raise Error("Image must be a string.")
        self.image = self.image.strip()
        if self.execution == 'agave' or self.execution == 'docker':
            pass
        else:
            raise Error("Invalid execution specified for task:{}. " +
                        "Valid options are: docker, agave.".format(self.name))
        if self.command:
            self.command = self.command.strip()

    def remote_inputs(self):
        """Return a list of TaskInput objects that are on remote servers."""


class AgaveDownloadTask(BaseDockerTask):
    """ Represents a task that executes a docker container to download a file on a remote server."""

    def __init__(self, obj, wf_name):
        # the GlobalInput or TaskOutput that should be downloaded
        self.obj = obj

        # either global inputs or the name of a task
        if isinstance(obj, GlobalInput):
            self.parent = 'inputs'
        else:
            self.parent = obj.task_name

        # name of the task
        self.name = 'download_{}.{}'.format(self.parent, self.obj.label)

        # the image for the download container
        self.image = 'jstubbs/eod_download'

        # description dictionary for creating the base object
        self.desc = {'inputs': ['{}.{} -> /agave/inputs/1'.format(self.parent, obj.label)],
                'outputs': ['/agave/outputs/1 -> {}.{}'.format(self.name, obj.label)],
                'image': self.image,
                }
        super(AgaveDownloadTask, self).__init__(self.name, self.desc, wf_name)

        # exactly one input; still go through parse_in_out_desc to keep things uniform.
        inp = self.parse_in_out_desc(self.inputs_desc, 'input')[0]
        self.inputs.append(TaskInput(src=inp[0], dest=inp[1]))
        # real_source is not computed for Download tasks, but it is trivial. Needs
        # to be the actual input
        self.inputs[0].real_source = obj
        # create the TaskOutput objects
        for out in self.parse_in_out_desc(self.outputs_desc, 'output'):
            self.outputs.append(TaskOutput(src=out[0],
                                           label=out[1],
                                           wf_name=wf_name,
                                           task_name=self.name))

        # notify obj that this is its download task
        obj.download_task = self


class AgaveAppTask(BaseDockerTask):
    """ Represents a task to execute an agave app by submitting a job. Translates a description of an
    Agave job into an execution of the eod_job_submit container, and therefore maintains all of the
    attributed required of a DockerTask (image, command, inputs, outputs, etc.) in addition to the
    attributes pertaining to the Agave app.
    """
    def __init__(self, name, desc, wf_name):
        super(AgaveAppTask, self).__init__(name, desc, wf_name)

        # app_id to submit
        self.app_id = desc.get('app_id')

        # parameters for the Agave app execution
        self.params_desc = desc.get('parameters')
        if not self.params_desc:
            self.params_desc = {}

        # image for the eod_job_submit container
        self.image = 'jstubbs/eod_job_submit'

        # build the command from the params
        self.command = self.get_container_command()

        # these are AgaveAppTaskInput objects, inputs to the Agave app, supplied by
        # the user in the yaml file.
        self.app_inputs = []

        # these are AgaveAppTaskOutput objects, outputs to the Agave app, supplied by
        # the user in the yaml file.
        self.app_outputs = []

        self.audit()

        # the inputs_desc is a dictionary whose keys are agave app input id's and whose values
        # are a list of sources (labels) to use.
        for inp_id, sources in self.inputs_desc.items():
            for idx, source_desc in enumerate(sources):
                app_inp = AgaveAppTaskInput(inp_id, source_desc, idx)
                self.app_inputs.append(app_inp)
                self.inputs.append(app_inp.task_input)

        # create the AgaveAppTaskOutput objects
        for out in self.parse_in_out_desc(self.outputs_desc, 'output'):
            if out[0].startswith('/'):
                raise Error('Agave app output sources must be relative paths.')
            app_out = AgaveAppTaskOutput(src=out[0], label=out[1], wf_name=wf_name, task_name=self.name)
            self.app_outputs.append(app_out)
            self.outputs.append(app_out.task_output)

        # we add an extra task input for AgaveAppTasks that contains the output files to be created (paths
        # in the container) by the eod_job_submit container.
        self.add_out_labels_input()

    def audit(self):
        """Run basic audits on a constructed task. Work in progress."""
        if not self.name:
            raise Error("Name required for every task.")
        if not self.app_id:
            raise Error("No app_id specified for task: {}".format(self.name))
        if not type(self.params_desc) == dict and not type(self.params_desc) == OrderedDict:
            raise Error("Parameters should be specified as a dictionary, got {} instead".format(type(self.params_desc)))

    def get_container_command(self):
        """Returns the command to run inside the eod_job_submit container."""
        cmd = 'python /eod_job_submit/submit.py '
        cmd += 'app_id={} '.format(self.app_id)
        print("Params: {}".format(self.params_desc))
        for k, v in self.params_desc.items():
            cmd += pipes.quote('{}={}'.format(k, v)) + ' '
        return cmd

    def add_out_labels_input(self):
        """Create a file containing the output paths and add it as a TaskInput."""
        host_path = os.path.join(get_host_work_dir(self.wf_name), self.name, AGAVE_OUTPUTS_DIR[1:], 'output_labels')
        base_dir = os.path.dirname(host_path)
        container_path = os.path.join(AGAVE_OUTPUTS_DIR, 'output_labels')
        inp = AddedInput(host_path=host_path, container_path=container_path)
        self.inputs.append(inp)
        if not os.path.exists(to_eod(base_dir)):
            print("Creating output_label input base_dir:{}".format(base_dir))
            os.makedirs(to_eod(base_dir))
        print("Creating output_labels file at:{} <-> {}".format(host_path, to_eod(host_path)))
        with open(to_eod(host_path), 'w') as f:
            for out in self.app_outputs:
                # print(out.task_output.src, file=f)
                print(out.src, file=f)

    def pre_action(self):
        """ Get a current access token right before executing"""
        self.envs = {'access_token': self.ae.ag.token.token_info['access_token'],
                     'refresh_token': self.ae.ag.token.token_info['refresh_token'],
                     'system_id': self.ae.storage_system,
                     'api_server': self.ae.ag.api_server,
                     'api_key': self.ae.ag.api_key,
                     'api_secret': self.ae.ag.api_secret,
                     'verify': self.ae.ag.verify}

class TaskFile(object):
    """
    Utility class for working with a yaml file that represents a docker
    workflow.
    """
    def __init__(self, yaml_file):
        if yaml_file[0] == '/':
            self.path = yaml_file
        else:
            self.path = os.path.join(os.getcwd(), yaml_file)
        self.basic_audits()
        self.get_top_level_objects()
        self.top_level_audits()
        self.work_dir = os.path.join(EOD_CONTAINER_BASE, self.name)
        self.tasks = []

    def basic_audits(self):
        """
        Basic audits of the yaml file. This is a work in progress.
        """
        if not os.path.exists(self.path):
            raise Error("Could not find input file: " + str(self.path))

    def get_top_level_objects(self):
        with open(self.path) as f:
            src = ordered_load(f)
            # get the name for this workflow:
            self.name = src.get('name')
            # the processes dictionary:
            self.proc_dict = src.get('processes')
            # the global inputs list:
            self.glob_ins = src.get('inputs')
            # the global outputs list:
            self.glob_outs = src.get('outputs')

    def top_level_audits(self):
        if not self.name:
            raise Error("Invalid yaml syntax: global name required.")

    def create_glob_ins(self):
        """
        Create global input objects from the yaml source.
        """
        self.global_inputs = []
        for inp_src in self.glob_ins:
            if not len(inp_src.split('<-')) == 2:
                raise Error("Invalid global input definition: " + str(inp_src))
            label, source = inp_src.split('<-')
            glob = GlobalInput(label.strip(), source.strip(), self.name)
            self.global_inputs.append(glob)

    def create_tasks(self):
        """
        Creates the task objects associated with the processes dictionary.
        """
        # first, create the tasks from their descriptions
        for name, src in self.proc_dict.items():
            task_type = src.get('execution', 'docker')
            if task_type == 'agave_app':
                task = AgaveAppTask(name, src, self.name)
            else:
                task = SimpleDockerTask(name, src, self.name)
            self.tasks.append(task)
        # once tasks are created, set real_source on the task inputs
        for task in self.tasks:
            for inp in task.inputs:
                inp.set_real_source(self.global_inputs, self.tasks)
        # once the real_sources have been set, determine if remote GlobalInputs and TaskOutputs are used locally,
        # and create a task to download them if necessary
        for inp in self.global_inputs:
            inp.set_used_locally(self.tasks)
            if inp.is_uri and inp.used_locally:
                self.tasks.append(AgaveDownloadTask(inp, self.name))
        for task in self.tasks:
            for out in task.outputs:
                out.set_used_locally(self.tasks)
                if out.is_uri and out.used_locally:
                    self.tasks.append(AgaveDownloadTask(out, self.name))
        # with these new download tasks created, the real sources for inputs could have changed. Update them:
        for task in self.tasks:
            # only matters for local tasks that aren't download tasks
            if not task.execution == 'docker' or isinstance(task, AgaveDownloadTask):
                continue
            for inp in task.inputs:
                if not inp.real_source:
                    raise Exception("input without real source: {}. task:{}".format(
                        inp.src, task.name))
                if inp.real_source.is_uri:
                    inp.real_source = inp.real_source.download_task.outputs[0]

        # finally, once all tasks are created, we can add the output volumes to each task, create an agave executor if
        # needed, and set the action
        for task in self.tasks:
            task.set_output_volume_mounts()
            task.set_input_volumes(self.global_inputs, self.tasks)
            # agave app tasks and download tasks get an AgaveAppExecutor so they use local_action_fn
            if isinstance(task, AgaveAppTask) or isinstance(task, AgaveDownloadTask):
                task.ae = AgaveAppExecutor(wf_name=self.name, create_home_dir=False)
                task.set_action(task.ae)
            # docker tasks with execution 'agave' use an AgaveExecutor with the
            elif task.execution == 'agave':
                task.ae = AgaveExecutor(wf_name=self.wf_name)
                task.set_action(task.ae)
            # plain docker task running locally; no executor
            else:
                task.set_action()
            task.set_doit_dict()


def parse_yaml(yaml_file):
    task_file = TaskFile(yaml_file)
    task_file.create_glob_ins()
    task_file.create_tasks()
    return task_file


class DockerLoader(TaskLoader):
    @staticmethod
    def load_tasks(cmd, opt_values, pos_args):
        cpus = multiprocessing.cpu_count()
        task_list = [dict_to_task(task.doit_dict) for task in tasks]
        config = {'verbosity': 2,
                  'dep_file': '{}/.doit.db'.format(EOD_CONTAINER_BASE)}
        if cpus > 1:
            config['num_process'] = cpus
            print("Using multiprocessing with {} processes.".format(cpus))
        return task_list, config


def ordered_load(stream, Loader=yaml.Loader, object_pairs_hook=OrderedDict):
    """
    Load a yaml description to json, preserving the order of the stanzas.
    """
    class OrderedLoader(Loader):
        pass
    def construct_mapping(loader, node):
        loader.flatten_mapping(node)
        return object_pairs_hook(loader.construct_pairs(node))
    OrderedLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
        construct_mapping)
    return yaml.load(stream, OrderedLoader)



def main(yaml_file):
    # parse yml file and add tasks to global 'tasks' variable
    task_file = parse_yaml(yaml_file)
    # load global tasks
    for task in task_file.tasks:
        tasks.append(task)
    # execute the doit engine.
    sys.exit(DoitMain(DockerLoader()).run(sys.argv[2:]))

if __name__ == '__main__':
    requests.packages.urllib3.disable_warnings()
    update_hosts()
    parser = argparse.ArgumentParser(description='Execute workflow of docker containers described in a yaml file.')
    parser.add_argument('yaml_file', type=str,
                        help='Yaml file to parse')
    parser.add_argument('--username', type=str,
                        help='username for running in the Agave cloud.')
    args = parser.parse_args()
    main(args.yaml_file)
    main()