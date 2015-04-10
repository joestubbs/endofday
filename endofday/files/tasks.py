import argparse
import os
import subprocess
import sys

from collections import OrderedDict
import yaml

from doit.task import dict_to_task
from doit.cmd_base import TaskLoader
from doit.doit_cmd import DoitMain

# working directory for endofday
BASE = os.environ.get('STAGING') or '/staging'

# global tasks list to pass to the DockerLoader
tasks = []

class Error(Exception):
    def __init__(self, msg = None):
        self.msg = msg
        sys.exit(msg)


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
        self.label = label
        self.src = src
        # src and host_path are the same for GlobalInputs for now, but
        # for composition of workflows, in general a global input could be
        # the global output of another workflow, so we want to distinguish.
        # For composition, and in particular, for this, we'll need a mechanism
        # for referencing an external workflow object.
        self.host_path = src
        # todo - need a way to resolve the workflow's label to a host path.


class Volume(object):
    """
    Represents a volume mounted into a container for a task.
    """
    def __init__(self, host_path, container_path):
        self.host_path = host_path
        self.container_path = container_path


class TaskInput(object):
    """
    Represents a file input to a task within a workflow.
    """
    def __init__(self, src, dest):
        self.src = src
        self.dest = dest
        if not len(src.split('.')) == 2:
            raise Error('Invalid source for task resource: ' + str(src)
                        + ' format is: <task>.<name>')
        # the task name should either be 'inputs' to refer to a global input
        # or it should be the name of another task.
        self.src_task = self.src.split('.')[0]
        self.src_name = self.src.split('.')[1]


class TaskOutput(object):
    """
    Represents a file output of a task within a workflow.
    """
    def __init__(self, src, label, task_name, wf_name):
        self.src = src
        self.label = label
        self.task_name = task_name
        # we assume container path is absolute -- if not, throw error for now
        if not self.src.startswith('/'):
            raise Error("Invalid output format - container paths must be absolute.")
        self.host_path = os.path.join(BASE, wf_name, self.task_name, self.src[1:])
        self.host_dir_path, self.container_dir_path = self.get_dir_paths()

    def get_dir_paths(self):
        """
        Determine path on the host corresponding to this output.
        """
        if self.host_path.endswith('/'):
            return self.host_path, self.src
        else:
            # mount the directory up one
            return os.path.abspath(os.path.join(self.host_path, '..' )), os.path.abspath(os.path.join(self.src, '..' ))

class Task(object):
    """
    Represents a pydoit task.
    """
    def __init__(self, name, desc, wf_name):
        """
        construct a task from a process definition yaml stanza.
        """
        # name of the task
        self.name = name
        # docker image to use
        self.image = desc.get('image')
        # command to run within the docker container
        self.command = desc.get('command')
        # user supplied description of the task
        self.description = desc.get('description')
        # whether to start up multiple containers when there are multiple inputs
        self.multiple = desc.get('multiple')
        # inputs descriptions
        self.inputs_desc = desc.get('inputs') or []
        # outputs description
        self.outputs_desc = desc.get('outputs') or []
        # the TaskInput objects
        self.get_inputs()
        # the TaskOutput objects
        self.get_outputs(wf_name)
        # the directories to mount for this task
        self.get_volume_dirs()

    def get_action(self):
        """
        The action for a task is the function that is actually called by
        pydoit to execute the task. It needs to do two things:
        1) create directories on the host for each volume_dir
        2) execute the docker run statement
        """
        def action_fn():
            for dir in self.volume_dirs:
                if not os.path.exists(dir.host_path):
                    print "creating: ", dir.host_path
                    os.makedirs(dir.host_path)
            docker_cmd = "docker run --rm"
            # order important here -- need to mount output dirs first so that
            # inputs overlay them.
            for volume in self.volume_dirs:
                docker_cmd += " -v " + volume.host_path + ":" + volume.container_path
            for volume in self.input_volumes:
                docker_cmd += " -v " + volume.host_path + ":" + volume.container_path
            # add the image:
            docker_cmd += ' ' + self.image
            # add the command:
            docker_cmd += ' ' + self.command
            print "Task:", self.name, " docker cmd: ", docker_cmd
            # run the container in another process
            proc = subprocess.Popen(docker_cmd, shell=True)
            proc.wait()

        self.action = action_fn

    def get_inputs(self):
        self.inputs = []
        for inp_desc in self.inputs_desc:
            if not len(inp_desc.split('->')) == 2:
                raise Error("Invalid input format in " + str(self.name) + ' process: ' + str(inp_desc) +
                            ' format is: <source> -> <destination>')
            src, dest = inp_desc.split('->')
            inp = TaskInput(src.strip(), dest.strip())
            self.inputs.append(inp)

    def get_outputs(self, wf_name):
        self.outputs = []
        for out_desc in self.outputs_desc:
            if not len(out_desc.split('->')) == 2:
                raise Error("Invalid output format in " + str(self.name) + ' process: ' + str(out_desc) +
                            ' format is: <source> -> <destination>')
            src, dest = out_desc.split('->')
            out = TaskOutput(src.strip(), dest.strip(), self.name, wf_name)
            self.outputs.append(out)

    def get_volume_dirs(self):
        """
        We create directories on the host and mount them into the container at
        run time so that we have access to the outputs. Each volume consists of
        two paths: the path on the host and the path in the container. For each
        output, we create a volume to mount that is the immediate parent
        directory containing the files unless it is a directory in which case
        we mount the directory itself. Note also that we may not need to mount
        anything if another output would mount the same or larger directory.
        """
        self.volume_dirs = []
        dirs_list = []
        for output in self.outputs:
            volume = Volume(host_path=output.host_dir_path,
                            container_path=output.container_dir_path)
            dirs_list.append(volume)
        dirs_list.sort(key= lambda vol:vol.container_path)
        # add volumes from dirs_list, removing extraneous ones
        for volume in dirs_list:
            head, tail = os.path.split(volume.container_path)
            while head and tail:
                if head in [volume.container_path for volume in self.volume_dirs]:
                    break
                head, tail = os.path.split(head)
            else:
                self.volume_dirs.append(volume)

    def get_input_volumes(self, global_inputs, tasks):
        """
        We mount the inputs to the process directly from their source which will
        either be the output of a prior task or a file on the local host (i.e.,
        a global input).
        """
        self.input_volumes = []
        for inp in self.inputs:
            sources = []
            # if src task is 'inputs', it is a global input:
            if inp.src_task == 'inputs':
                # look up the input in the global inputs.
                sources = global_inputs
            else:
                # look up the input in the outputs of anther task
                for task in tasks:
                    if task.name == inp.src_task:
                        sources = task.outputs
            if not sources:
                raise Error("Input reference not found: " + str(inp.src_task))

            # iterate through the source list to find the matching resource:
            for source in sources:
                if source.label == inp.src_name:
                    volume = Volume(host_path=source.host_path,
                                    container_path=inp.dest)
                    self.input_volumes.append(volume)
                    break

    def get_doit_dict(self):
        """
        Returns a dictionary that can be used to generate a doit task.
        """
        file_deps = [volume.host_path for volume in self.input_volumes]
        targets = [output.host_path for output in self.outputs]
        self.doit_dict = {
            'name': self.name,
            'actions': [self.action],
            'doc': self.description,
            'targets': targets,
            'file_dep': file_deps,
        }

class DockerLoader(TaskLoader):
    @staticmethod
    def load_tasks(cmd, opt_values, pos_args):
        task_list = [dict_to_task(task.doit_dict) for task in tasks]
        config = {'verbosity': 2}
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
        self.path = os.path.join(os.getcwd(), yaml_file)
        self.basic_audits()
        self.get_top_level_objects()
        self.top_level_audits()
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
            self.global_inputs.append(GlobalInput(label.strip(),
                                                  source.strip()))

    def create_tasks(self):
        """
        Creates a the task objects associated with the processes dictionary.
        """
        for name, src in self.proc_dict.items():
            self.tasks.append(Task(name, src, self.name))

    def create_actions(self):
        """
        Adds volumes and actions to each task now that the task file has been
        parsed once.
        """
        for task in self.tasks:
            # the input volumes (file mounts)
            task.get_input_volumes(self.global_inputs, self.tasks)
            # the pydoit action associated with this task
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
    parser = argparse.ArgumentParser(description='Execute workflow of docker containers described in a yaml file.')
    parser.add_argument('yaml_file', type=str,
                        help='Yaml file to parse')
    args = parser.parse_args()
    main(args.yaml_file)
    main()