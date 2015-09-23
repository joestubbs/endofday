#!/bin/bash
# eod-agaveapps-step1

# first, sleep for the provided amount of time
sleep ${sleep}

# create a new output file
touch output1.txt

# cat inputs to outputs, adding some text.
cat ${step_1_inp} >> output1.txt
echo "Step 1 added this line" >> output1.txt