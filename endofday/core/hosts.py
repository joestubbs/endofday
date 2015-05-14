# update hosts file in the container with a specified server and IP
import urlparse

from .config import Config


def update_hosts():
    ip = Config.get('agave', 'api_server_ip')
    if not ip:
        return
    api_server = Config.get('agave', 'api_server')
    api_server = urlparse.urlparse(api_server).netloc
    with open('/etc/hosts', 'a') as f:
        f.write('\n' + ip + "   " + api_server)
