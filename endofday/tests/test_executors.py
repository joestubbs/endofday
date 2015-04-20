"""
Tests for the executors module.
"""

import pytest

import agavepy


@pytest.fixture(scope='session')
def agave(credentials):
    ag = agavepy.agave.Agave(resources=credentials['resources'],
                  username=credentials['username'],
                  password=credentials['password'],
                  api_server=credentials['apiserver'],
                  api_key=credentials['apikey'],
                  api_secret=credentials['apisecret'],
                  verify=credentials.get('verify_certs', True))
    ag.token.create()
    return ag


