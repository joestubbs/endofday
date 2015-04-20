#
# Implements support for remote execution platforms such as agave.

import os
from agavepy.agave import Agave

from .error import Error
from .config import Config

class AgaveExecutor(object):
    """Execute a task in the Agave cloud"""

    def __init__(self, wf_name, url=None, username=None, password=None,
                 client_name=None, client_key=None, client_secret=None,
                 storage_system=None, home_dir=None):
        self.from_config()
        if not url:
            url = self.api_server
        if not username:
            username = self.username
        if not password:
            password = self.password
        if not client_name:
            client_name = self.client_name
        if not client_key:
            client_key = self.client_key
        if not client_secret:
            client_secret = self.client_secret
        if not storage_system:
            storage_system = self.storage_system
        if not home_dir:
            home_dir = self.home_dir
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

    def from_config(self):
        """
        Parses config file and updates instance.
        :return:
        """
        # required args
        self.api_server = Config.get('agave', 'api_server')
        if not self.api_server:
            raise Error('Invalid config: api_server is required.')
        self.username = Config.get('agave', 'username')
        if not self.username:
            raise Error('Invalid config: username is required.')
        self.password = Config.get('agave', 'password')
        if not self.password:
            raise Error('Invalid config: password is required.')

        # optional args:
        self.client_key = Config.get('agave', 'client_key')
        self.client_secret = Config.get('agave', 'client_secret')
        self.storage_system = Config.get('agave', 'storage_system')
        if not self.storage_system:
            self.storage_system = 'data.iplantcollaborative.org'
        self.home_dir = Config.get('agave', 'home_dir')

    def create_dir(self, path):
        """Create a directory on the configured storage system inside the endofday working
        directory. The path argument should be a relative path; a leading slash will be removed.
        """
        if path.startswith('/'):
            path = path[1:]
        path = os.path.join(self.working_dir, path)
        try:
            rsp = self.ag.files.manage(systemId=self.storage_system,
                                       filePath=self.home_dir,
                                       body={'action':'mkdir',
                                             'path':path})
        except Exception as e:
            raise Error("Error creating directory on default storage system. Path: " + path +
                        "Msg:" + str(e))

    def upload_file(self, local_path, remote_path):
        """Upload a file on the local system to remote storage. The remote_path param should
        be relative to the endofday working dir. The local_path should be absolute.
        """
        sourcefilePath = os.join(self.working_dir, remote_path)
        try:
            self.ag.importData(systemId=self.storage_system,
                               filePath=sourcefilePath,
                               fileToUpload=open(local_path,'rb'))
        except Exception as e:
            raise Error("Upload to default storage failed - local_path: " + local_path +
                        "; remote_path: " + remote_path + "; Msg:" + str(e))