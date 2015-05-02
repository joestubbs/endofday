import os

# are we running in docker
RUNNING_IN_DOCKER = False
if os.environ.get('RUNNING_IN_DOCKER'):
    RUNNING_IN_DOCKER = True

# the base directory for the endofday docker container
DOCKER_BASE = '/staging'
