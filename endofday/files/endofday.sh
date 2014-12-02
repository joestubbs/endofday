#!/bin/bash

ARG=$1

cd /endofday
python /endofday/nf.py $STAGING/$ARG
/nextflow run "${ARG%.*}.nf"
