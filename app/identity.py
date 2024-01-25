from flask_jwt_extended import create_access_token

def create_jwt(user):
    identity = {'id': user['_id'], 'username': user['username'], 'email': user['email'], 'roles': user['roles']}
    access_token = create_access_token(identity=identity)
    return access_token