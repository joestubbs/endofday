# Utilities for authn/z
import base64
import json
import re

from Crypto.Signature import PKCS1_v1_5
from Crypto.PublicKey import RSA
from Crypto.Hash import SHA256
from flask import g, request, abort
from flask_restful import Resource
import jwt

from config import Config
from errors import PermissionsException
from models import Actor, get_permissions
from request_utils import APIException, ok, RequestParser
from stores import actors_store, permissions_store


jwt.verify_methods['SHA256WITHRSA'] = (
    lambda msg, key, sig: PKCS1_v1_5.new(key).verify(SHA256.new(msg), sig))
jwt.prepare_key_methods['SHA256WITHRSA'] = jwt.prepare_RS_key


def get_pub_key():
    pub_key = Config.get('web', 'apim_public_key')
    return RSA.importKey(base64.b64decode(pub_key))


PUB_KEY = get_pub_key()

TOKEN_RE = re.compile('Bearer (.+)')


def get_pub_key():
    pub_key = Config.get('web', 'apim_public_key')
    return RSA.importKey(base64.b64decode(pub_key))


def authn_and_authz():
    """All-in-one convenience function for implementing the basic abaco authentication
    and authorization on a flask app. Use as follows:

    import auth

    my_app = Flask(__name__)
    @my_app.before_request
    def authnz_for_my_app():
        auth.authn_and_authz()

    """
    authentication()
    authorization()


def authentication():
    """Entry point for authentication. Use as follows:

    import auth

    my_app = Flask(__name__)
    @my_app.before_request
    def authn_for_my_app():
        auth.authentication()

    """
    # don't control access to OPTIONS verb
    if request.method == 'OPTIONS':
        return
    access_control_type = Config.get('web', 'access_control')
    if access_control_type == 'none':
        g.user = 'anonymous'
        g.token = 'N/A'
        g.tenant = request.headers.get('tenant') or Config.get('web', 'tenant_name')
        g.api_server = get_api_server(g.tenant)
        return
    if access_control_type == 'jwt':
        return check_jwt(request)
    abort(400, {'message': 'Invalid access_control'})


def check_jwt(req):
    tenant_name = None
    jwt_header = None
    for k, v in req.headers.items():
        if k.startswith('X-Jwt-Assertion-'):
            tenant_name = k.split('X-Jwt-Assertion-')[1]
            jwt_header = v
            break
    else:
        # never found a jwt; look for 'Assertion'
        try:
            jwt_header = req.headers['Assertion']
            tenant_name = 'dev_staging'
        except KeyError:
             msg = ''
             for k,v in req.headers.items():
                msg = msg + ' ' + str(k) + ': ' + str(v)
             abort(400, {'message': 'JWT header missing. Headers: '+msg})
    try:
        decoded = jwt.decode(jwt_header, PUB_KEY)
        g.jwt = jwt_header
        g.tenant = tenant_name.upper()
        g.api_server = get_api_server(tenant_name)
        g.user = decoded['http://wso2.org/claims/enduser']
        g.token = get_token(req.headers)
    except (jwt.DecodeError, KeyError):
        abort(400, {'message': 'Invalid JWT.'})

def get_api_server(tenant_name):
    # todo - lookup tenant in tenants table
    if tenant_name.upper() == 'AGAVE-PROD':
        return 'https://public.agaveapi.co'
    if tenant_name.upper() == 'ARAPORT-ORG':
        return 'https://api.araport.org'
    if tenant_name.upper() == 'DESIGNSAFE':
        return 'https://agave.designsafe-ci.org'
    if tenant_name.upper() == 'DEV-STAGING':
        return 'https://dev.tenants.staging.agaveapi.co'
    if tenant_name.upper() == 'IPLANTC-ORG':
        return 'https://agave.iplantc.org'
    if tenant_name.upper() == 'IREC':
        return 'https://irec.tenants.prod.agaveapi.co'
    if tenant_name.upper() == 'TACC-PROD':
        return 'https://api.tacc.utexas.edu'
    if tenant_name.upper() == 'VDJSERVER-ORG':
        return 'https://vdj-agave-api.tacc.utexas.edu'
    return 'https://dev.tenants.staging.agaveapi.co'

def get_token(headers):
    """
    :type headers: dict
    :rtype: str|None
    """
    auth = headers.get('Authorization', '')
    match = TOKEN_RE.match(auth)
    if not match:
        return None
    else:
        return match.group(1)

def authorization():
    """Entry point for authorization. Use as follows:

    import auth

    my_app = Flask(__name__)
    @my_app.before_request
    def authz_for_my_app():
        auth.authorization()

    """
    if request.method == 'OPTIONS':
        # allow all users to make OPTIONS requests
        return

    # all other checks are based on actor-id; if that is not present then let
    # request through to fail.
    actor_id = request.args.get('actor_id', None)
    if not actor_id:
        return

    if request.method == 'GET':
        has_pem = check_permissions(user=g.user, actor_id=actor_id, level='READ')
    else:
        # creating a new actor requires no permissions
        print(request.url_rule.rule)
        if request.method == 'POST' \
                and ('actors' == request.url_rule.rule or 'actors/' == request.url_rule.rule):
            has_pem = True
        else:
            has_pem = check_permissions(user=g.user, actor_id=actor_id, level='UPDATE')
    if not has_pem:
        raise APIException("Not authorized")

def check_permissions(user, actor_id, level):
    """Check the permissions store for user and level"""
    permissions = get_permissions(actor_id)
    for pem in permissions:
        if pem['user'] == user:
            if pem['level'] >= level:
                return True
    return False
