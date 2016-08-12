# A basic server to execute eod workflows.

from flask import Flask
from flask_cors import CORS

from request_utils import EodApi
from controllers import ActorResource, ActorStateResource, ActorsResource, \
    ActorExecutionsResource, ActorExecutionResource, \
    ActorExecutionLogsResource
from auth import authn_and_authz


app = Flask(__name__)
CORS(app)
api = AbacoApi(app)

# Authn/z
@app.before_request
def auth():
    authn_and_authz()


# Resources
api.add_resource(ActorsResource, '/workflows')
api.add_resource(ActorResource, '/workflows/<string:workflow_id>')

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
