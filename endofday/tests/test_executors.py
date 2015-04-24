"""
Tests for the executors module.
"""

import os
import pytest
from endofday.core.executors import AgaveExecutor

SYSTEM_ID = 'data.iplantcollaborative.org'

HERE = os.path.dirname(os.path.abspath((__file__)))

@pytest.fixture(scope='session')
def ae():
    ae = AgaveExecutor(wf_name='test_suite_wf')
    return ae


def test_create_dir(ae):
    # first, delete the test dir just in case it is already there:
    try:
        ae.ag.files.deleteFromDefaultSystem(sourcefilePath='jstubbs/test_suite_wf/algebra')
    except:
        pass
    # create the directory:
    ae.create_dir('algebra/add_5/data')
    # check that it exists:
    rsp = ae.ag.files.listOnDefaultSystem(filePath='jstubbs/test_suite_wf')
    assert type(rsp) == list
    rsp = ae.ag.files.listOnDefaultSystem(filePath='jstubbs/test_suite_wf/algebra')
    assert type(rsp) == list
    rsp = ae.ag.files.listOnDefaultSystem(filePath='jstubbs/test_suite_wf/algebra/add_5')
    assert type(rsp) == list

def test_upload_file(ae):
    # first, delete the test file just in case it is already there:
    try:
        ae.ag.files.deleteFromDefaultSystem(sourcefilePath='jstubbs/test_suite_wf/algebra/add_5/sample_input.txt')
    except:
        pass
    # create the test directory
    try:
        ae.create_dir('algebra/add_5/data')
    except:
        pass
    # upload the file
    rsp = ae.upload_file(local_path=os.path.join(HERE,'sample_input.txt'), remote_path='algebra/add_5/data')
    # returns an AgaveAsyncResponse - timeout after 120 seconds
    assert rsp.result(120) == 'COMPLETE'
    # check that the file is there:
    rsp = ae.ag.files.listOnDefaultSystem(filePath='jstubbs/test_suite_wf/algebra/add_5/data')
    assert type(rsp) == list
    result = [r for r in rsp if r['name'] == 'sample_input.txt']
    assert len(result) > 0

def test_download_file(ae):
    rsp = ae.download_file(local_path=os.path.join(HERE,'sample_input.txt'), remote_path='algebra/add_5/data/sample_input.txt')
    assert rsp.get('status') == 'success'





