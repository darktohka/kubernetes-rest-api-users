from flask import request
import jwt

jwt_secret = None

def get_jwt_secret():
    return jwt_secret

def set_jwt_secret(secret):
    print('Set JWT secret:', secret)

    global jwt_secret
    jwt_secret = secret

def create_jwt(user):
    identity = {'id': user['_id'], 'username': user['username'], 'email': user['email'], 'roles': user['roles']}
    access_token = jwt.encode(identity, get_jwt_secret(), algorithm='HS256')
    return access_token

def get_jwt_identity():
    headers = request.headers
    bearer = headers.get('Authorization')
    token = bearer.split()[1]
    return jwt.decode(token, get_jwt_secret(), algorithms=['HS256'])