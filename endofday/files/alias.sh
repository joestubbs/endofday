#!/bin/bash

docker run -v $(pwd):/staging -e STAGING_DIR=$(pwd) --rm -v /var/run/docker.sock:/var/run/docker.sock jstubbs/endofday $*