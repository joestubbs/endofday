import json
import os
import pytest

from endofday.core.tasks import parse_yaml, ordered_load
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
    assert context.get('wf_name') == 'add_5'
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

def test_gen_task_defn(ae, task_file):
    task = task_file.tasks[0]
    path = ae.gen_task_defn(task)
    assert path == '/staging/test_suite_wf/add_5/add_5.yml'
    task_yml = ordered_load(open(path, 'rb'))
    assert task_yml.get('name') == 'add_5'
    assert len(task_yml.get('inputs')) == 1
    inp = task_yml.get('inputs')[0]
    assert inp == 'input_0 <- input.txt'
    procs = task_yml.get('processes')
    assert len(procs) == 1
    proc = procs[0]
    # print proc
    # import pdb; pdb.set_trace()
    src = proc.get('add_5')
    assert src.get('image') == 'jstubbs/add_n'
    assert len(src.get('inputs')) == 1
    assert src.get('inputs')[0] == 'inputs.input_0 -> /data/input.txt'
    assert len(src.get('outputs')) == 1
    assert src.get('outputs')[0] == '/data/output.txt -> output'
    assert src.get('command') == 'python add_n.py -i 5'


def test_job(ae, task_file):
    task = task_file.tasks[0]
    job = ae.get_job(task)
    job_json = json.loads(job)
    assert job_json.get('name') == 'eod-test_suite_wf-add_5'
    wf_input = job_json.get('inputs').get('wf')
    assert len(wf_input) == 1
    wf = wf_input[0]
    assert wf == 'agave://data.iplantcollaborative.org//jstubbs/test_suite_wf/add_5/add_5.yml'
    glob_inputs = job_json.get('inputs').get('glob_in')
    assert len(glob_inputs) == 1
    assert glob_inputs[0] == 'agave://data.iplantcollaborative.org//jstubbs/test_suite_wf/global_inputs/input.txt'
