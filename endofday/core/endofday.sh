#!/bin/bash

ARG=$1

if [ $ARG = "--setup" ]; then
  cp /core/alias.sh /staging/endofday.sh
  chmod +x /staging/endofday.sh
else
  cd /
  python -m core.tasks $STAGING/$ARG
  # This used only for the nf backend
#  /nextflow run "${ARG%.*}.nf"
fi
