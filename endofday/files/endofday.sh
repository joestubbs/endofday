#!/bin/bash

ARG=$1

if [ $ARG = "--setup" ]; then
  cp /endofday/alias.sh /staging/endofday.sh
  chmod +x /staging/endofday.sh
else
  cd /endofday
  python /endofday/tasks.py $STAGING/$ARG
  /nextflow run "${ARG%.*}.nf"
fi
