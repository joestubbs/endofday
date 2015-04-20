"""
Tests for the executors module.
"""

import pytest

from endofday.core.executors import AgaveExecutor

SYSTEM_ID = 'data.iplantcollaborative.org'

@pytest.fixture(scope='session')
def ae():
    ae = AgaveExecutor(wf_name='test_suite_wf')
    return ae


def test_create_dir(ae):
    # first, delete the test dir just in case it is already there:
    try:
        ae.ag.files.deleteFromDefaultSystem(sourcefilePath='jstubbs/test_suite_wf')
    except:
        pass
    # create the directory:
    ae.create_dir('test_suite_wf/algebra/add_5/data')
    # check that it exists:
    rsp = ae.ag.files.listOnDefaultSystem(filePath='jstubbs/test_suite_wf')
    assert len(rsp) > 0
    rsp = ae.ag.files.listOnDefaultSystem(filePath='jstubbs/test_suite_wf/algrebra')
    assert len(rsp) > 0
    rsp = ae.ag.files.listOnDefaultSystem(filePath='jstubbs/test_suite_wf/algrebra/add_5')
    assert len(rsp) > 0



