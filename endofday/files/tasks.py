import argparse
import sys

from doit.task import dict_to_task
from doit.cmd_base import TaskLoader
from doit.doit_cmd import DoitMain


# global tasks list to pass to the DoitLoader
tasks = []

class Error(Exception):
    def __init__(self, msg = None):
        self.msg = msg


class GlobalInput(object):
    """
    Represents an input to a workflow.
    """
    def __init__(self, name, src):
        self.name = name
        self.src = src


class Volume(object):
    """
    Represents a volume mounted into a container for a task.
    """
    def __init__(self):


class TaskResource(object):
    """
    Represents a file input or output of a task within a workflow.
    """
    def __init__(self, src, dest):
        self.src = src
        self.dest = dest
        if not len(src.split('.')) == 2:
            raise Error('Invalid source for task resource: ' + str(src) + ' format is: <task>.<name>')
        self.src_task = self.src.split('.')[0]
        self.src_name = self.src.split('.')[1]


class Task(object):
    """
    Represents a pydoit task.
    """
    def __init__(self, name, desc):
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

        self.get_derived_values()

    def get_derived_values(self):
        self.action = self.get_action()
        self.inputs = self.get_inputs()
        self.outputs = self.get_outputs()
        self.volumes = self.get_volumes()

    def get_action(self):
        #@todo
        return "echo " + self.name

    def get_inputs(self):
        self.inputs = []
        for inp_desc in self.inputs_desc:
            if not len(inp_desc.split('->')) == 2:
                raise Error("Invalid input format in " + str(self.name) + ' process: ' + str(inp_desc) +
                            ' format is: <source> -> <destination>')
            src, dest = inp_desc.split('->')
            inp = TaskResource(src.strip(), dest.strip())
            self.inputs.append(inp)

    def get_outputs(self):
        self.outputs = []
        for out_desc in self.outputs_desc:
            if not len(out_desc.split('->')) == 2:
                raise Error("Invalid input format in " + str(self.name) + ' process: ' + str(out_desc) +
                            ' format is: <source> -> <destination>')
            src, dest = out_desc.split('->')
            out = TaskResource(src.strip(), dest.strip())
            self.outputs.append(out)

    def get_volumes(self):
        """
        Determine the set of volumes that need to be mounted into the container.
        """

    def doit_dict(self):
        """
        Returns a dictionary that can be used to generate a doit task.
        """
        return {
            'name': self.name,
            'actions': [self.action],
            'doc': self.description,
            'targets': [],
            'file_dep': [],
        }

class DoitLoader(TaskLoader):
    @staticmethod
    def load_tasks(cmd, opt_values, pos_args):
        task_list = [dict_to_task(task.doit_dict()) for task in tasks]
        config = {'verbosity': 2}
        return task_list, config


def main(yaml_file):
    pass

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Execute workflow of docker containers described in a yaml file.')
    parser.add_argument('yaml_file', type=str,
                        help='Yaml file to parse')
    args = parser.parse_args()
    main(args.yaml_file)
    main()