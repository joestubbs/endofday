"""
Tests for the tasks module.

To run the tests:
1. Make sure endofday.conf has necessary fields for interacting with iplant.
2. If not putting them in the config, export AGAVE_CLIENT_SECRET and AGAVE_PASSWORD as env vars.
3. Activate the endofday virtualenv and execute
    $ py.test test_tasks.py
   from within this directory.

"""

import os
import pytest

from endofday.core.tasks import parse_yaml

HERE = os.path.dirname(os.path.abspath((__file__)))

@pytest.fixture(scope='session')
def task_file():
    task_file = parse_yaml(os.path.join(HERE, 'sample_wf.yml'))
    return task_file

def test_basic_task_file_attrs(task_file):
    assert task_file.path == os.path.join(HERE, 'sample_wf.yml')
    assert task_file.name == 'test_suite_wf'
    assert task_file.executor == 'local'

def test_global_inputs(task_file):
    assert len(task_file.global_inputs) == 2
    glob_in = task_file.global_inputs[0]
    assert glob_in.label == 'input'
    assert glob_in.host_path == '/home/jstubbs/github-repos/endofday/examples/input.txt'
    assert glob_in.src == '/home/jstubbs/github-repos/endofday/examples/input.txt'
    assert glob_in.eod_rel_path == os.path.join('test_suite_wf', 'global_inputs', 'input.txt')

    glob_in = task_file.global_inputs[1]
    assert glob_in.label == 'loc_in'
    assert glob_in.host_path == '/staging/loc_in.txt'
    assert glob_in.src == 'loc_in.txt'
    assert glob_in.eod_rel_path == os.path.join('test_suite_wf', 'global_inputs', 'loc_in.txt')

def test_tasks_length(task_file):
    assert len(task_file.tasks) == 3

def test_tasks_names_and_order(task_file):
    assert task_file.tasks[0].name == 'add_5'
    assert task_file.tasks[1].name == 'mult_3'
    assert task_file.tasks[2].name == 'sum'


# add_5 tests
def test_add_5_task_basic(task_file):
    task = task_file.tasks[0]
    assert task.name == 'add_5'
    assert task.image == 'jstubbs/add_n'
    assert task.command == 'python add_n.py -i 5'
    assert task.description == 'Add 5 to all inputs.'
    assert task.multiple == None
    assert task.execution == 'local'

def test_add_5_inputs(task_file):
    task = task_file.tasks[0]
    assert len(task.inputs) == 1
    inp = task.inputs[0]
    assert inp.src == 'inputs.input'
    assert inp.dest == '/data/input.txt'
    assert inp.src_name == 'input'
    assert inp.src_task == 'inputs'

def test_add_5_outputs(task_file):
    task = task_file.tasks[0]
    assert len(task.outputs) == 1
    out = task.outputs[0]
    assert out.src == '/data/output.txt'
    assert out.label == 'output'
    assert out.task_name == 'add_5'
    assert out.eod_rel_path == 'test_suite_wf/add_5/data/output.txt'
    assert out.eod_rel_dir_path == 'test_suite_wf/add_5/data'
    assert out.host_path == '/staging/test_suite_wf/add_5/data/output.txt'
    assert out.host_dir_path == '/staging/test_suite_wf/add_5/data'

def test_add_5_volume_dirs(task_file):
    task = task_file.tasks[0]
    assert len(task.volume_dirs) == 1
    vdir = task.volume_dirs[0]
    assert vdir.container_path == '/data'
    assert vdir.eod_rel_path == 'test_suite_wf/add_5/data'
    assert vdir.host_path == '/staging/test_suite_wf/add_5/data'

def test_add_5_input_volumes(task_file):
    task = task_file.tasks[0]
    assert len(task.input_volumes) == 1
    inpv = task.input_volumes[0]
    assert inpv.container_path == '/data/input.txt'
    assert inpv.eod_rel_path == 'test_suite_wf/global_inputs/input.txt'
    assert inpv.host_path == '/home/jstubbs/github-repos/endofday/examples/input.txt'


def test_add_5_docker_command(task_file):
    task = task_file.tasks[0]
    cmd, _, _ = task.get_docker_command()
    assert cmd == 'docker run --rm -v /staging/test_suite_wf/add_5/data:/data -v /home/jstubbs/github-repos/endofday/examples/input.txt:/data/input.txt jstubbs/add_n python add_n.py -i 5'


# mult_3 tests
def test_mult_3_task_basic(task_file):
    task = task_file.tasks[1]
    assert task.name == 'mult_3'
    assert task.image == 'jstubbs/mult_n'
    assert task.command == 'python mult_n.py -f 3'
    assert task.description == 'Multiply all inputs by 3.'
    assert task.multiple == None
    assert task.execution == 'local'

def test_mult_3_inputs(task_file):
    task = task_file.tasks[1]
    assert len(task.inputs) == 1
    inp = task.inputs[0]
    assert inp.src == 'add_5.output'
    assert inp.dest == '/tmp/input'
    assert inp.src_name == 'output'
    assert inp.src_task == 'add_5'

def test_mult_3_outputs(task_file):
    task = task_file.tasks[1]
    assert len(task.outputs) == 4
    out = task.outputs[0]
    assert out.src == '/tmp/foo/bar/output'
    assert out.label == 'output1'
    assert out.task_name == 'mult_3'
    assert out.eod_rel_path == 'test_suite_wf/mult_3/tmp/foo/bar/output'
    assert out.eod_rel_dir_path == 'test_suite_wf/mult_3/tmp/foo/bar'
    assert out.host_path == '/staging/test_suite_wf/mult_3/tmp/foo/bar/output'
    assert out.host_dir_path == '/staging/test_suite_wf/mult_3/tmp/foo/bar'

    out = task.outputs[1]
    assert out.src == '/tmp/foo/baz/output'
    assert out.label == 'output2'
    assert out.task_name == 'mult_3'
    assert out.eod_rel_path == 'test_suite_wf/mult_3/tmp/foo/baz/output'
    assert out.eod_rel_dir_path == 'test_suite_wf/mult_3/tmp/foo/baz'
    assert out.host_path == '/staging/test_suite_wf/mult_3/tmp/foo/baz/output'
    assert out.host_dir_path == '/staging/test_suite_wf/mult_3/tmp/foo/baz'

    out = task.outputs[2]
    assert out.src == '/tmp/foo/output'
    assert out.label == 'output3'
    assert out.task_name == 'mult_3'
    assert out.eod_rel_path == 'test_suite_wf/mult_3/tmp/foo/output'
    assert out.eod_rel_dir_path == 'test_suite_wf/mult_3/tmp/foo'
    assert out.host_path == '/staging/test_suite_wf/mult_3/tmp/foo/output'
    assert out.host_dir_path == '/staging/test_suite_wf/mult_3/tmp/foo'

    out = task.outputs[3]
    assert out.src == '/tmp/output'
    assert out.label == 'output'
    assert out.task_name == 'mult_3'
    assert out.eod_rel_path == 'test_suite_wf/mult_3/tmp/output'
    assert out.eod_rel_dir_path == 'test_suite_wf/mult_3/tmp'
    assert out.host_path == '/staging/test_suite_wf/mult_3/tmp/output'
    assert out.host_dir_path == '/staging/test_suite_wf/mult_3/tmp'

def test_mult_3_volume_dirs(task_file):
    task = task_file.tasks[1]
    assert len(task.volume_dirs) == 1
    vdir = task.volume_dirs[0]
    assert vdir.container_path == '/tmp'
    assert vdir.eod_rel_path == 'test_suite_wf/mult_3/tmp'
    assert vdir.host_path == '/staging/test_suite_wf/mult_3/tmp'

def test_mult_3_input_volumes(task_file):
    task = task_file.tasks[1]
    assert len(task.input_volumes) == 1
    inpv = task.input_volumes[0]
    assert inpv.container_path == '/tmp/input'
    assert inpv.eod_rel_path == 'test_suite_wf/add_5/data/output.txt'
    assert inpv.host_path == '/staging/test_suite_wf/add_5/data/output.txt'

def test_mult_3_docker_command(task_file):
    task = task_file.tasks[1]
    cmd, _, _ = task.get_docker_command()
    assert cmd == 'docker run --rm -v /staging/test_suite_wf/mult_3/tmp:/tmp -v /staging/test_suite_wf/add_5/data/output.txt:/tmp/input jstubbs/mult_n python mult_n.py -f 3'

# sum tests
def test_sum_task_basic(task_file):
    task = task_file.tasks[2]
    assert task.name == 'sum'
    assert task.image == 'jstubbs/sum'
    assert task.command == 'python sum.py'
    assert task.description == 'Sum all inputs.'
    assert task.multiple == None
    assert task.execution == 'local'

def test_sum_inputs(task_file):
    task = task_file.tasks[2]
    assert len(task.inputs) == 2
    inp = task.inputs[0]
    assert inp.src == 'mult_3.output'
    assert inp.dest == '/data/in.txt'
    assert inp.src_name == 'output'
    assert inp.src_task == 'mult_3'
    inp = task.inputs[1]
    assert inp.src == 'inputs.loc_in'
    assert inp.dest == '/data/loc_in'
    assert inp.src_name == 'loc_in'
    assert inp.src_task == 'inputs'
