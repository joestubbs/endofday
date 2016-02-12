"""
Tests for the tasks module.

To run the tests:
1. Create an endofday.conf in the cwd (the /tests directory) with all necessary fields for interacting with the public tenant.
2. If not putting them in the config, export AGAVE_CLIENT_SECRET and AGAVE_PASSWORD as env vars.
3. Leave the  -e STAGING_DIR=/testsuite/cwd/on/host as is: this is used by the test suite to ensure the paths are computed
   correctly.
4. Build the latest image as jstubbs/eod (or jstubbs/eod-alpine and update the command below) and run tests using:
    $ docker run --rm -it --entrypoint=py.test -v /:/host -v $(pwd):/staging -e RUNNING_IN_DOCKER=true -e STAGING_DIR=/testsuite/cwd/on/host jstubbs/eod /tests/test_tasks.py
"""

import os
import pytest
import sys

sys.path.append('/')

from core.tasks import parse_yaml, TaskFile

HERE = os.path.dirname(os.path.abspath((__file__)))

@pytest.fixture(scope='session')
def task_file():
    tf_path = os.path.join(HERE, 'sample_wf.yml')
    task_file = parse_yaml(tf_path)
    # task_file = TaskFile(tf_path)
    # task_file.create_glob_ins()
    # task_file.create_tasks()
    return task_file

@pytest.fixture(scope='session')
def agave_task_file():
    tf_path = os.path.join(HERE, 'sample_agave_wf.yml')
    agave_task_file = parse_yaml(tf_path)
    # task_file = TaskFile(tf_path)
    # task_file.create_glob_ins()
    # task_file.create_tasks()
    return agave_task_file


def test_basic_task_file_attrs(task_file):
    assert task_file.path == os.path.join(HERE, 'sample_wf.yml')
    assert task_file.name == 'test_suite_wf'
    assert task_file.glob_ins[0] == 'input <- /home/jstubbs/github-repos/endofday/examples/input.txt'
    assert task_file.glob_ins[1] == 'loc_in <- loc_in.txt'
    assert task_file.global_inputs[0].label == 'input'
    assert task_file.global_inputs[1].src == 'loc_in.txt'
    assert task_file.global_inputs[1].label == 'loc_in'

def test_global_inputs(task_file):
    assert len(task_file.global_inputs) == 2
    glob_in = task_file.global_inputs[0]
    assert glob_in.label == 'input'
    assert glob_in.abs_host_path == '/home/jstubbs/github-repos/endofday/examples/input.txt'
    assert glob_in.src == '/home/jstubbs/github-repos/endofday/examples/input.txt'
    assert glob_in.eod_container_path == '/host/home/jstubbs/github-repos/endofday/examples/input.txt'

    glob_in = task_file.global_inputs[1]
    assert glob_in.label == 'loc_in'
    assert glob_in.abs_host_path == '/testsuite/cwd/on/host/loc_in.txt'
    assert glob_in.src == 'loc_in.txt'
    assert glob_in.eod_container_path == '/staging/loc_in.txt'

def test_tasks_length(task_file):
    assert len(task_file.tasks) == 3
#
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
    assert task.execution == 'docker'

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
    assert out.eod_container_path == '/staging/test_suite_wf/add_5/data/output.txt'
    assert out.abs_host_path == '/testsuite/cwd/on/host/test_suite_wf/add_5/data/output.txt'

def test_add_5_output_volume_mounts(task_file):
    task = task_file.tasks[0]
    assert len(task.output_volume_mounts) == 1
    vmount = task.output_volume_mounts[0]
    assert vmount.container_path == '/data'
    assert vmount.host_path == '/testsuite/cwd/on/host/test_suite_wf/add_5/data'

def test_add_5_input_volumes(task_file):
    task = task_file.tasks[0]
    assert len(task.input_volumes) == 1
    inpv = task.input_volumes[0]
    assert inpv.container_path == '/data/input.txt'
    assert inpv.host_path == '/home/jstubbs/github-repos/endofday/examples/input.txt'

def test_add_5_docker_command(task_file):
    task = task_file.tasks[0]
    cmd, _, _ = task.get_docker_command()
    assert cmd == 'docker run --rm -v /testsuite/cwd/on/host/test_suite_wf/add_5/data:/data -v /home/jstubbs/github-repos/endofday/examples/input.txt:/data/input.txt jstubbs/add_n python add_n.py -i 5'


# mult_3 tests
def test_mult_3_task_basic(task_file):
    task = task_file.tasks[1]
    assert task.name == 'mult_3'
    assert task.image == 'jstubbs/mult_n'
    assert task.command == 'python mult_n.py -f 3'
    assert task.description == 'Multiply all inputs by 3.'
    assert task.execution == 'docker'

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
    assert out.eod_container_path == '/staging/test_suite_wf/mult_3/tmp/foo/bar/output'
    assert out.abs_host_path == '/testsuite/cwd/on/host/test_suite_wf/mult_3/tmp/foo/bar/output'

    out = task.outputs[1]
    assert out.src == '/tmp/foo/baz/output'
    assert out.label == 'output2'
    assert out.task_name == 'mult_3'
    assert out.eod_container_path == '/staging/test_suite_wf/mult_3/tmp/foo/baz/output'
    assert out.abs_host_path == '/testsuite/cwd/on/host/test_suite_wf/mult_3/tmp/foo/baz/output'

    out = task.outputs[2]
    assert out.src == '/tmp/foo/output'
    assert out.label == 'output3'
    assert out.task_name == 'mult_3'
    assert out.eod_container_path == '/staging/test_suite_wf/mult_3/tmp/foo/output'
    assert out.abs_host_path == '/testsuite/cwd/on/host/test_suite_wf/mult_3/tmp/foo/output'

    out = task.outputs[3]
    assert out.src == '/tmp/output'
    assert out.label == 'output'
    assert out.task_name == 'mult_3'
    assert out.eod_container_path == '/staging/test_suite_wf/mult_3/tmp/output'
    assert out.abs_host_path == '/testsuite/cwd/on/host/test_suite_wf/mult_3/tmp/output'

def test_mult_3_volume_dirs(task_file):
    task = task_file.tasks[1]
    assert len(task.output_volume_mounts) == 1
    vdir = task.output_volume_mounts[0]
    assert vdir.container_path == '/tmp'
    assert vdir.host_path == '/testsuite/cwd/on/host/test_suite_wf/mult_3/tmp'

def test_mult_3_input_volumes(task_file):
    task = task_file.tasks[1]
    assert len(task.input_volumes) == 1
    inpv = task.input_volumes[0]
    assert inpv.container_path == '/tmp/input'
    assert inpv.host_path == '/testsuite/cwd/on/host/test_suite_wf/add_5/data/output.txt'

def test_mult_3_docker_command(task_file):
    task = task_file.tasks[1]
    cmd, _, _ = task.get_docker_command()
    assert cmd == 'docker run --rm -v /testsuite/cwd/on/host/test_suite_wf/mult_3/tmp:/tmp -v /testsuite/cwd/on/host/test_suite_wf/add_5/data/output.txt:/tmp/input jstubbs/mult_n python mult_n.py -f 3'

# sum tests
def test_sum_task_basic(task_file):
    task = task_file.tasks[2]
    assert task.name == 'sum'
    assert task.image == 'jstubbs/sum'
    assert task.command == 'python sum.py'
    assert task.description == 'Sum all inputs.'
    assert task.execution == 'docker'

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



# agave_task_file tests
def test_agave_basic_task_file_attrs(agave_task_file):
    assert agave_task_file.path == os.path.join(HERE, 'sample_agave_wf.yml')
    assert agave_task_file.name == 'test_suite_wf'
    assert agave_task_file.glob_ins[0] == 'input <- agave://ex.storage.system//data/input.txt'
    assert agave_task_file.glob_ins[1] == 'input_2 <- agave://other.storage.system//home/jdoe/foo'
    assert agave_task_file.global_inputs[0].label == 'input'
    assert agave_task_file.global_inputs[0].src == 'agave://ex.storage.system//data/input.txt'
    assert agave_task_file.global_inputs[1].src == 'agave://other.storage.system//home/jdoe/foo'
    assert agave_task_file.global_inputs[1].label == 'input_2'

def test_agave_global_inputs(agave_task_file):
    assert len(agave_task_file.global_inputs) == 2
    glob_in = agave_task_file.global_inputs[0]
    assert glob_in.label == 'input'
    assert glob_in.is_uri
    assert glob_in.uri == 'agave://ex.storage.system//data/input.txt'

    glob_in = agave_task_file.global_inputs[1]
    assert glob_in.label == 'input_2'
    assert glob_in.is_uri
    assert glob_in.uri == 'agave://other.storage.system//home/jdoe/foo'

def test_agave_tasks_length(agave_task_file):
    assert len(agave_task_file.tasks) == 2

def test_agave_tasks_names_and_order(agave_task_file):
    assert agave_task_file.tasks[0].name == 'add_5'
    assert agave_task_file.tasks[1].name == 'mult_n'

# add_5 tests
def test_agave_add_5_task_outputs(agave_task_file):
    task = agave_task_file.tasks[0]
    assert len(task.outputs) == 1
    out = task.outputs[0]
    assert out.src == '/agave/outputs/output_id_1'
    assert out.label == 'some_output'
    assert out.task_name == 'add_5'
    assert out.eod_container_path == '/staging/test_suite_wf/add_5/agave/outputs/output_id_1'
    assert out.abs_host_path == '/testsuite/cwd/on/host/test_suite_wf/add_5/agave/outputs/output_id_1'

def test_agave_add_5_output_volume_mounts(agave_task_file):
    task = agave_task_file.tasks[0]
    assert len(task.output_volume_mounts) == 1
    vmount = task.output_volume_mounts[0]
    assert vmount.container_path == '/agave/outputs'
    assert vmount.host_path == '/testsuite/cwd/on/host/test_suite_wf/add_5/agave/outputs'

def test_agave_add_5_input_volumes(agave_task_file):
    task = agave_task_file.tasks[0]
    assert len(task.input_volumes) == 3 # one more than the actual number of inputs
    inpv = task.input_volumes[0]
    assert inpv.container_path == '/agave/inputs/input_id_1/0'
    assert inpv.host_path == '/testsuite/cwd/on/host/test_suite_wf/global_inputs/input'

    inpv = task.input_volumes[1]
    assert inpv.container_path == '/agave/inputs/input_id_1/1'
    assert inpv.host_path == '/testsuite/cwd/on/host/test_suite_wf/global_inputs/input_2'

    inpv = task.input_volumes[2]
    assert inpv.container_path == '/agave/outputs/output_labels'
    assert inpv.host_path == '/testsuite/cwd/on/host/test_suite_wf/add_5/agave/outputs/output_labels'

def test_agave_add_5_docker_command(agave_task_file):
    task = agave_task_file.tasks[0]
    cmd, _, _ = task.get_docker_command()
    assert cmd == 'docker run --rm -v /testsuite/cwd/on/host/test_suite_wf/add_5/agave/outputs:/agave/outputs -v /testsuite/cwd/on/host/test_suite_wf/global_inputs/input:/agave/inputs/input_id_1/0 -v /testsuite/cwd/on/host/test_suite_wf/global_inputs/input_2:/agave/inputs/input_id_1/1 -v /testsuite/cwd/on/host/test_suite_wf/add_5/agave/outputs/output_labels:/agave/outputs/output_labels jstubbs/eod_job_submit python /eod_job_submit/submit.py app_id=add_n some_param_id=1 some_other_param_id=verbose '

# mult_n tests
def test_agave_mult_n_task_outputs(agave_task_file):
    task = agave_task_file.tasks[1]
    assert len(task.outputs) == 1
    out = task.outputs[0]
    assert out.src == '/agave/outputs/some_output_id'
    assert out.label == 'just_some_label'
    assert out.task_name == 'mult_n'
    assert out.eod_container_path == '/staging/test_suite_wf/mult_n/agave/outputs/some_output_id'
    assert out.abs_host_path == '/testsuite/cwd/on/host/test_suite_wf/mult_n/agave/outputs/some_output_id'

def test_agave_mult_n_output_volume_mounts(agave_task_file):
    task = agave_task_file.tasks[1]
    assert len(task.output_volume_mounts) == 1
    vmount = task.output_volume_mounts[0]
    assert vmount.container_path == '/agave/outputs'
    assert vmount.host_path == '/testsuite/cwd/on/host/test_suite_wf/mult_n/agave/outputs'

def test_agave_mult_n_input_volumes(agave_task_file):
    task = agave_task_file.tasks[1]
    assert len(task.input_volumes) == 4 # one more than the actual number of inputs
    inpv = task.input_volumes[0]
    assert inpv.container_path == '/agave/inputs/some_input_id/0'
    assert inpv.host_path == '/testsuite/cwd/on/host/test_suite_wf/add_5/agave/outputs/output_id_1'

    inpv = task.input_volumes[1]
    assert inpv.container_path == '/agave/inputs/some_input_id/1'
    assert inpv.host_path == '/testsuite/cwd/on/host/test_suite_wf/global_inputs/input'

    inpv = task.input_volumes[2]
    assert inpv.container_path == '/agave/inputs/some_other_input_id/0'
    assert inpv.host_path == '/testsuite/cwd/on/host/test_suite_wf/global_inputs/input_2'

    inpv = task.input_volumes[3]
    assert inpv.container_path == '/agave/outputs/output_labels'
    assert inpv.host_path == '/testsuite/cwd/on/host/test_suite_wf/mult_n/agave/outputs/output_labels'
