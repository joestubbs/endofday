#
# Implements support for remote execution platforms such as agave.

import os
from agavepy.agave import Agave
from .error import Error


class AgaveExecutor(object):
    """Execute a task in the Agave cloud"""

    def __init__(self, url, username, password, wf_name,
                 client_name=None, client_key=None, client_secret=None,
                 storage_system='data.iplantcollaborative.org', home_dir=None):
        self.ag = Agave(api_server=url, username=username, password=password,
                        client_name=client_name, api_key=client_key, api_secret=client_secret)
        self.storage_system = storage_system
        self.wf_name = wf_name
        if home_dir == '/':
            raise Error('Invalid home_dir: /, path must be relative to ')
        self.home_dir = home_dir
        # default the home directory to the username
        if not self.home_dir:
            self.home_dir = username
        self.working_dir = os.path.join(self.home_dir, wf_name)

    def create_dir(self, path):
        """Create a directory on the default storage system inside the endofday working
        direcotry. The path argument should be a relative path; a leading slash will be removed.
        """
        if path.startswith('/'):
            path = path[1:]
        path = os.path.join(self.working_dir, path)
        try:
            rsp = self.ag.files.manageOnDefaultSystem(sourcefilePath=self.home_dir,
                                                      body={'action':'mkdir',
                                                            'path':path})
        except Exception as e:
            raise Error("Error creating directory on default storage system. Path: " + path +
                        "Msg:" + str(e))

    def upload_file(self, local_path, remote_path):
        """Upload a file on the local system to remote storage. The remote_path param should
        be relative to the endofday working dir. The local_path should be absolute.
        """
        try:
            self.ag.importToDefaultSystem()
        except Exception as e:
            raise Error("Uplaod to default storage failed - local_path: " + local_path +
                        "; remote_path: " + remote_path + "; Msg:" + str(e))