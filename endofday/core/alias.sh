#!/bin/bash
cmd=$(which docker)
docker run -t -v /:/host -v $(pwd):/staging -v $cmd:/usr/bin/docker -e RUNNING_IN_DOCKER=true -e STAGING_DIR=$(pwd) --rm -v /var/run/docker.sock:/var/run/docker.sock jstubbs/eod $*