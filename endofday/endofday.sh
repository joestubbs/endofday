#!/bin/bash

ARG=$1

python /endofday/nf.py $ARG
/nextflow run "${ARG%.*}.nf"
