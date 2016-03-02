#!/bin/bash
cmd=$(which docker)
version=$(docker version -f '{{.Server.APIVersion}}')
docker run -t -v /:/host -v $(pwd):/staging -e DOCKER_API_VERSION=$version -e AGAVE_USERNAME=$username -e RUNNING_IN_DOCKER=true -e STAGING_DIR=$(pwd) --rm -v /var/run/docker.sock:/var/run/docker.sock jstubbs/eod $*