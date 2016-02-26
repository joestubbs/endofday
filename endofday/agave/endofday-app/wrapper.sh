#!/bin/bash
chmod +x endofday.sh
export username=${AGAVE_JOB_OWNER}
echo "username is:" $username
./endofday.sh ${wf}