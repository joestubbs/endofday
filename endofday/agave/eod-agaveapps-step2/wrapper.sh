#!/bin/bash
# eod-agaveapps-step2

# create a new output file
touch first_out.txt

# cat inputs to outputs, adding some text.
cat ${first_inp} >> first_out.txt
echo "Step 2 added this line" >> first_out.txt
