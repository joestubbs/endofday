# A basic python client for interacting with a remote eod-server. Relies on the agavepy sdk.

# usage:
# import the main class
# from endofday.remote.client import EodClient
#
# use the default agpy file configured for the client
# eod = EodClient()
#
# or, optionally, pass a path to a specific .agpy file
# eod = EodClient(path='/path/to/.agpy')
#
# list all your workflows
# eod.workflows.list()
#
# submit a workflow
# wf = eod.workflows.submit(wf_path='/path/to/workflow.yml')
#
# check the status
# status = eod.workflows.status(wf)

