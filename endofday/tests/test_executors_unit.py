import os
import pytest

from endofday.core.tasks import parse_yaml
from endofday.core.executors import AgaveExecutor

SYSTEM_ID = 'data.iplantcollaborative.org'

HERE = os.path.dirname(os.path.abspath((__file__)))

@pytest.fixture(scope='session')
def ae():
    ae = AgaveExecutor(wf_name='test_suite_wf')
    return ae

@pytest.fixture(scope='session')
def task_file():
    task_file = parse_yaml(os.path.join(HERE, 'sample_wf.yml'))
    return task_file

def test_task_context(ae, task_file):
    task = task_file.tasks[0]
    context = ae.get_task_context(task)
    glob_ins = context.get('global_inputs')
    assert len(glob_ins) == 1
    glob_inp = glob_ins[0]
    assert glob_inp['label'] == 'input_0'
    assert glob_inp['src'] == 'input.txt'
    processes = context.get('processes')
    assert len(processes) == 1
    process = processes[0]
    assert process['name'] == 'add_5'
    assert process['image'] == 'jstubbs/add_n'
    assert process['command'] == 'python add_n.py -i 5'
    inputs = process['inputs']
    assert len(inputs) == 1
    inp = inputs[0]
    assert inp['label'] == 'inputs.input_0'
    assert inp['dest'] == '/data/input.txt'

    outputs = process['outputs']
    assert len(outputs) == 1
    out = outputs[0]
    assert out['label'] == 'output'
    assert out['src'] == '/data/output.txt'

# def test_job(ae, task_file):
#     task = task_file.task[0]
#     job = ae.get_job(task)
#     with open(os.path.join(HERE, 'test_job.json'), 'rb') as f:
#         job_str = f.read()
#     assert job == job_str

