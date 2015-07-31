# This script submits a job to Agave as part of an eod workflow execution.
#
# usage: python submit.py app_id=<app_id> param_1=val_1 ... param_n=val_n
# where param_j is the id of a parameter to the Agave app with id app_id
#
# This script looks for files in the /agave/inputs directory whose names are the id's of the inputs
# and whose contents are the URIs to pass to the agave job.

# compiles a job template with the following:
#   app_id: the app to submit to
#   system_id: the system to archive to
#   inputs: list of objects with the following:
#       id: the id for the input
#       uris: list of objects with the following:
#           - uri_str: the full URI including quotes and trailing comma,
#                      e.g. "agave://example.orf//data/input.txt",
#
#   parameters: list of objects with the following:
#       id: the id for the parameter
#       value: the value for the parameter; this needs to be the proper JSON object with quotes and trailing commas.



from __future__ import print_function


def main():
    pass

if __name__ == '__main__':
    main()