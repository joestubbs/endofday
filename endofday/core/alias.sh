#!/bin/bash

docker run -t -v /:/host -v $(pwd):/staging -e RUNNING_IN_DOCKER=true -e STAGING_DIR=$(pwd) --rm -v /var/run/docker.sock:/var/run/docker.sock jstubbs/eod $*