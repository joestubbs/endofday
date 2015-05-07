#!/bin/bash

ARG=$1

if [ $ARG = "--setup" ]; then
  cp /core/alias.sh /staging/endofday.sh
  chmod +x /staging/endofday.sh
  cp /endofday.conf /staging/endofday.conf
elif [ $ARG = "--agave" ]; then
  python -m core.agaverun $STAGING/$2
else
  cd /
  python -m core.tasks $STAGING/$ARG $2
  # This used only for the nf backend
#  /nextflow run "${ARG%.*}.nf"
fi
