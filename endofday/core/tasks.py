import argparse
import multiprocessing
import os
import subprocess
import sys

from collections import OrderedDict
import requests
import yaml

from doit.task import dict_to_task
from doit.cmd_base import TaskLoader
from doit.doit_cmd import DoitMain

from .config import Config
from .error import Error
from .executors import AgaveAsyncResponse, AgaveExecutor
from .hosts import update_hosts

# working directory for endofday
# BASE = os.environ.get('STAGING_DIR') or '/staging'

# Current working directory of the host, passed in as an environmental variable by the alias.sh
HOST_BASE = os.environ.get('STAGING_DIR')

# the directory in the eod container that contains the current working directory of the host
EOD_CONTAINER_BASE = '/staging'

def to_eod(host_path):
    """Convert an absolute path on the host to an absolute path in the eod container"""
    if host_path.startswith(HOST_BASE):
        return host_path.replace(HOST_BASE, EOD_CONTAINER_BASE)
    else:
        return os.path.join('/host', host_path[1:])


# the directory where the eod_submit_job container will look for inputs'
AGAVE_INPUTS_DIR = '/agave/inputs'

# the directory where the eod_submit_job container will look for inputs'
AGAVE_OUTPUTS_DIR = '/agave/outputs'


from .docker import RUNNING_IN_DOCKER, DOCKER_BASE

# global tasks list to pass to the DockerLoader
tasks = []

verbose = False

class GlobalInput(object):
    """
    Represents an input to a workflow. E.g.
    input <- /data/foo/input.txt
    src =  /data/foo/input.txt
    label = input

    Could also be:
    input <- workflow1.output (and then we need to resolve this)

    """
    def __init__(self, label, src):
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
        if '://' in self.src:
            self.is_uri = True
            self.uri = self.src

        if not self.is_uri:
            # if src is an absolute path, look for the file in the /host dir of the eod container
            if self.src.startswith('/'):
                self.abs_host_path = self.src
                self.eod_container_path = to_eod(self.src)
            # otherwise, it's a relative path so it will be in the EOD_CONTAINER_BASE
            else:
                self.abs_host_path = os.path.join(HOST_BASE, self.src)
                self.eod_container_path = os.path.join(EOD_CONTAINER_BASE, self.src)


class Volume(object):
    """
    Represents a volume mounted into a container for a task.
    """
    def __init__(self, host_path, container_path):
        self.host_path = host_path
        self.container_path = container_path

    def to_str(self):
        """ Return a string that can be used in a docker command. """
        return '{}:{} '.format(self.host_path, self.container_path)


class BaseInput(object):
    """ Base class for TaskInput and AgaveAppTaskInput
    """
    def __init__(self, src):
        # src is a reference to either a global input or an output of another task.
        self.src = src

        if not len(src.split('.')) == 2:
            raise Error('Invalid source for task resource: ' + str(src)
                        + ' format is: <task>.<name>')
        # the task name should either be 'inputs' to refer to a global input
        # or it should be the name of another task.
        self.src_task = self.src.split('.')[0]
        self.src_name = self.src.split('.')[1]

    def resolve_src(self, global_inputs, tasks):
        """Resolves the src to a global input or task output."""
        if self.src_task == 'inputs':
            # src references a global input, so look through global_inputs
            sources = global_inputs
        else:
            # src references another task output
            for task in tasks:
                if task.name == self.src_task:
                    sources = task.outputs
                    break
            else:
                # didn't find the task label
                Error("Input reference not found: " + str(self.src_task))
        for source in sources:
            if source.label == self.src_name:
                return source
        else: # this is on for loop: if we did not break, we did not find the input
            raise Error("Input reference not found: " + str(self.src_task))


class TaskInput(BaseInput):
    """
    Represents a file input to a task within a workflow.
    """
    def __init__(self, src, dest):
        # Handle the src data
        super(TaskInput).__init__(self, src)

        # dest is a container path
        self.dest = dest

    def get_volume(self, global_inputs, tasks):
        """ Create a volume object for this task input."""
        real_source = self.resolve_src(global_inputs, tasks)
        host_path = real_source.abs_host_path
        container_path = self.dest
        return Volume(host_path, container_path)


class TaskOutput(object):
    """
    Represents a file output of a task within a workflow.
    """
    def __init__(self, src, label, wf_name, task_name):
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

    def get_volume(self):
        """ Create a volume object for this task output."""

        return Volume(host_path=self.host_directory,
                      container_path=os.path.split(self.src)[0])


class AgaveAppTaskInput(BaseInput):
    """
    Represents an input to a task which is of execution type 'agave_app'
    """
    def __init__(self, src, input_id):
        # Handle the src data
        super(TaskInput).__init__(self, src)

        # reference to an agave app input_id
        self.input_id = input_id

        # create a task input for the eod_submit_job container
        self.task_input = TaskInput(src=self.src, dest=os.path.join(AGAVE_INPUTS_DIR, self.input_id))

    def get_uri(self, global_inputs, tasks):
        """Get the absolute uri for this input which can be passed to the Agave job submission"""
        real_source = self.resolve_src(global_inputs, tasks)
        self.uri = real_source.uri


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

        # the uri for this output
        self.uri = self.get_uri()

        # create a task output for the eod_submit_job container
        self.task_output = TaskOutput(src=os.path.join(AGAVE_OUTPUTS_DIR, self.label),
                                      label=self.label,
                                      wf_name=self.wf_name,
                                      task_name=self.task_name)

        def get_uri(self):
            """ Return a URI for this output."""
            # todo -- need a way to get the URI for an output of an agave job.
            return ''


class BaseTask(object):
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
            result.append((src, dest))
        return result

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
        input_str = ' '
        for inp in self.inputs:
            input_str += inp.volume.to_str()
        docker_cmd += input_str
        if envs:
            for k,v in envs.items():
                docker_cmd += ' -e ' + '"' + str(k) + '=' + str(v) + '"'
        # add the image:
        docker_cmd += ' ' + self.image
        # add the command:
        docker_cmd += ' ' + self.command
        return docker_cmd, output_str, input_str

    def get_action(self, executor=None):
        """
        The action for a task is the function that is actually called by
        pydoit to execute the task.
        """

        def local_action_fn():
            """
            Execute the docker container on the local machine.
            """
            docker_cmd, _, _ = self.get_docker_command()
            # now, execute the container
            proc = subprocess.Popen(docker_cmd, shell=True)
            proc.wait()

        # if the task instance has its own executor, use that:
        if hasattr(self, 'executor'):
            self.action = self.executor.get_action(self)
        # otherwise, if we were passed a (global) executor, use that:
        elif executor:
            self.action = executor.get_action(self)
        # otherwise, use the local action
        else:
            self.action = local_action_fn

    def get_doit_dict(self):
        """
        Returns a dictionary that can be used to generate a doit task.
        """
        file_deps = []
        targets = []
        # pydoit paths need to refer to the endofday container:
        for inp in self.inputs:
            file_deps.append(to_eod(inp.host_path))

        ### HERE #####
        for output in self.outputs:
            if BASE in output.host_path:
                targets.append(output.host_path.replace(BASE, '/staging'))
            elif output.host_path.startswith('/'):
                targets.append(os.path.join('/host', output.host_path[1:]))
            else:
                targets.append(os.path.join('/host', output.host_path))
        self.doit_dict = {
            'name': self.name,
            'actions': [self.action],
            'doc': self.description,
            'targets': targets,
            'file_dep': file_deps,
        }


class DockerTask(BaseTask):
    """ Represents a task that executes a docker container.
    """
    def __init__(self, name, desc, wf_name):
        super(DockerTask).__init__(self, name, desc, wf_name)

        # docker image to use
        self.image = desc.get('image')

        # command to run within the docker container
        self.command = desc.get('command')

        # whether to run locally or in the Agave cloud
        self.execution = desc.get('execution') or 'local'

        self.audit()

        if self.execution == 'agave':
            self.executor = AgaveExecutor(wf_name=wf_name)

        # create the TaskInput objects
        for inp in self.parse_in_out_desc(self.inputs_desc, 'input'):
            self.inputs.append(TaskInput(src=inp[0], dest=inp[1]))

        # create the TaskOutput objects
        for out in self.parse_in_out_desc(self.outputs_desc, 'output'):
            self.outputs.append(TaskOutput(src=out[0],
                                           label=out[1],
                                           wf_name=wf_name,
                                           task_name=self.name))

        # the directories to mount for this task
        self.output_volume_mounts = self.get_output_volume_mounts()

    def audit(self):
        """Run basic audits on a constructed task. Work in progress."""
        if not self.name:
            raise Error("Name required for every task.")
        if not self.image:
            raise Error("No image specified for task: " + self.name)
        if self.execution == 'agave' or self.execution == 'local':
            pass
        else:
            raise Error("Invalid execution specified for task:{}. " +
                        "Valid options are: local, agave.".format(self.name))

    def get_output_volume_mounts(self):
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
        return result


class AgaveAppTask(BaseTask):
    """ Represents a task to execute an agave app by submitting a job.
    """
    def __init__(self, name, desc, wf_name):
        super(AgaveAppTask).__init__(self, name, desc, wf_name)

        # app_id to submit
        self.app_id = desc.get('app_id')

        # parameters for the Agave app execution
        self.params_desc = desc.get('parameters')

        # image for the eod_job_submit container
        self.image = 'jstubbs/eod_job_submit'

        # build the command from the params
        self.command = self.get_container_command()

        self.audit()

        # create the AgaveAppTaskInput objects
        for inp in self.parse_in_out_desc(self.inputs_desc, 'input'):
            self.inputs.append(AgaveAppTaskInput(src=inp[0], input_id=inp[1]))

        # create the AgaveAppTaskOutput objects
        for out in self.parse_in_out_desc(self.outputs_desc, 'output'):
            self.outputs.append(AgaveAppTaskOutput(src=out[0],
                                                   label=out[1],
                                                   wf_name=wf_name,
                                                   task_name=self.name))

    def audit(self):
        """Run basic audits on a constructed task. Work in progress."""
        if not self.name:
            raise Error("Name required for every task.")
        if not self.app_id:
            raise Error("No app_id specified for task: {}".format(self.name))
        if not type(self.params_desc) == dict:
            raise Error("Parameters should be specified as a dictionary.")

    def get_container_command(self):
        """Returns the command to run inside the eod_job_submit container."""
        cmd = 'python submit.py /agave/output_labels '
        cmd += 'app_id={} '.format(self.app_id)
        for k, v in self.params_desc.items():
            cmd += '{}={} '.format(k, v)
        return cmd

















class Task(object):
    """
    Represents a pydoit task.
    """

    def get_doit_dict(self):
        """
        Returns a dictionary that can be used to generate a doit task.
        """
        file_deps = []
        targets = []
        if RUNNING_IN_DOCKER:
            # pydoit paths need to refer to the endofday container if endofday is running in docker:
            for volume in self.input_volumes:
                file_deps.append(volume.docker_host_path)
            for output in self.outputs:
                if BASE in output.host_path:
                    targets.append(output.host_path.replace(BASE, '/staging'))
                elif output.host_path.startswith('/'):
                    targets.append(os.path.join('/host', output.host_path[1:]))
                else:
                    targets.append(os.path.join('/host', output.host_path))
        else:
            file_deps = [volume.host_path for volume in self.input_volumes]
            targets = [output.host_path for output in self.outputs]
        self.doit_dict = {
            'name': self.name,
            'actions': [self.action],
            'doc': self.description,
            'targets': targets,
            'file_dep': file_deps,
        }
        # print "Task:", self.name
        # print "BASE:", BASE
        # print "file_deps:", str(file_deps)
        # print "outputs:", str(targets)

class DockerLoader(TaskLoader):
    @staticmethod
    def load_tasks(cmd, opt_values, pos_args):
        cpus = multiprocessing.cpu_count()
        task_list = [dict_to_task(task.doit_dict) for task in tasks]
        config = {'verbosity': 2}
        if cpus > 1:
            config['num_process'] = cpus
            print "Using multiprocessing with", cpus, "processes."
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
        self.executor = 'local'
        # create an agave executor
        if Config.get('execution', 'execution') == 'agave':
            self.executor = 'agave'
            self.ae = AgaveExecutor(wf_name=self.name)
            self.ae.create_dir(path='global_inputs')
        # the task objects associated with this workflow.
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
            self.global_inputs.append(GlobalInput(label.strip(), source.strip()))

    def create_tasks(self):
        """
        Creates a the task objects associated with the processes dictionary.
        """
        for name, src in self.proc_dict.items():
            task = Task(name, src, self.name)
            task.audit()
            self.tasks.append(task)

    def create_actions(self):
        """
        Adds volumes and actions to each task now that the task file has been
        parsed once.
        """
        for task in self.tasks:
            # the input volumes (file mounts)
            task.get_input_volumes(self.global_inputs, self.tasks)
            # the pydoit action associated with this task
            if self.executor == 'agave':
                task.get_action(self.ae)
            else:
                task.get_action()
            task.get_doit_dict()

def parse_yaml(yaml_file):
    task_file = TaskFile(yaml_file)
    task_file.create_glob_ins()
    task_file.create_tasks()
    task_file.create_actions()
    return task_file


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
    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true')
    parser.set_defaults(verbose=False)
    args = parser.parse_args()
    verbose = args.verbose
    if verbose:
        print 'RUNNING_IN_DOCKER:', RUNNING_IN_DOCKER
    main(args.yaml_file)
    main()