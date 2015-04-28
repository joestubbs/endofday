#!/bin/bash

ARG=$1
VERB=$2

if [ $ARG = "--setup" ]; then
  cp /core/alias.sh /staging/endofday.sh
  chmod +x /staging/endofday.sh
else
  cd /
  python -m core.tasks $STAGING/$ARG $VERB
  # This used only for the nf backend
#  /nextflow run "${ARG%.*}.nf"
fi
