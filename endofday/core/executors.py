#
# Implements support for remote execution platforms such as agave.

import os
import requests
import time

from agavepy.agave import Agave

from .error import Error
from .config import Config

class TimeoutError(Error):
    pass

class AgaveAsyncResponse(object):
    """
    Implements parts of the concurrent.futures.Future interface for nonblocking Agave responses.
    """
    def __init__(self, ag, response):
        """Construct an asynchronous response object from an Agave response which should be an agavepy.agave.AttrDict
        """
        self.ag = ag
        self.status = response.status
        self.url = response._links.get('history').get('href')
        if not self.url:
            raise Error("Error parsing response object: no URL detected. response: " + str(response))
        # url's returned by agave sometimes have the version as 2.0, so we replace that here
        self.url = self.url.replace('/2.0/','/v2/')

    def _update_status(self):
        headers = {'Authorization': 'Bearer ' + self.ag.token.token_info.get('access_token')}
        rsp = requests.get(url=self.url, headers=headers)
        if not rsp.status_code == 200:
            import pdb; pdb.set_trace()
            raise Error("Error updating status; invalid status code:  " + str(rsp.status_code) + str(rsp.content))
        result = rsp.json().get('result')
        if not result:
            raise Error("Error updating status: " + str(rsp))
        # if the transfer ever completed, we'll call it good:
        if len([x for x in result if 'COMPLETE' in x['status']]) > 0:
            self.status = 'COMPLETE'
        else:
            # sort on creation time of the history object
            result = sorted(result, key=lambda k: k['created'])
            self.status = result[0].get('status')

    def _is_done(self):
        return self.status == 'COMPLETE' or self.status == 'STAGING_FAILED'

    def done(self):
        """Return True if the call was successfully cancelled or finished running."""
        self._update_status()
        return self._is_done()

    def result(self, timeout=None):
        """
        Returns the result of the original call, blocking until the result is returned or the timeout parameter is
        reached. The timeout paramter is interpreted in seconds.
        :param timeout:
        :return:
        """
        if self._is_done():
            return self.status
        self._update_status()
        now = time.time()
        if timeout:
            future = now + timeout
        else:
            future = float("inf")
        while time.time() < future:
            time.sleep(1)
            self._update_status()
            if self._is_done():
                return self.status
        raise TimeoutError()


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
        self.home_dir = home_dir
        # default the home directory to the username
        if not self.home_dir:
            self.home_dir = username
        self.working_dir = os.path.join(self.home_dir, wf_name)
        # create the working directory now
        rsp = self.ag.files.manage(systemId=self.storage_system,
                                   filePath=self.home_dir,
                                   body={'action':'mkdir',
                                         'path':wf_name})

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
        self.client_name = Config.get('agave', 'client_name')
        if not self.client_name:
            raise Error('Invalid config: client_name is required.')

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
        try:
            rsp = self.ag.files.manage(systemId=self.storage_system,
                                       filePath=self.working_dir,
                                       body={'action':'mkdir',
                                             'path':path})
        except Exception as e:
            raise Error("Error creating directory on default storage system. Path: " + path +
                        "Msg:" + str(e))
        return rsp

    def upload_file(self, local_path, remote_path):
        """Upload a file on the local system to remote storage. The remote_path param should
        be relative to the endofday working dir. The local_path should be absolute.
        """
        sourcefilePath = os.path.join(self.working_dir, remote_path)
        try:
            rsp = self.ag.files.importData(systemId=self.storage_system,
                                           filePath=sourcefilePath,
                                           fileToUpload=open(local_path,'rb'))
        except Exception as e:
            raise Error("Upload to default storage failed - local_path: " + local_path +
                        "; remote_path: " + remote_path + "; Msg:" + str(e))
        import pdb; pdb.set_trace()
        return AgaveAsyncResponse(self.ag, rsp)