from flask import Flask, jsonify
from flask_pymongo import PyMongo
from flask_jwt_extended import JWTManager
import json
import os


try:
    connection_string = os.environ['MONGO_CONNECTION_STRING']
    discord_redirect_uri = os.environ['DISCORD_REDIRECT_URI']
    discord_client_id = os.environ['DISCORD_CLIENT_ID']
    discord_client_secret = os.environ['DISCORD_CLIENT_SECRET']
    jwt_secret_key = os.environ['JWT_SECRET_KEY']
except KeyError:
    with open('.env', 'r') as f:
        env = json.load(f)

    connection_string = env['MONGO_CONNECTION_STRING']
    discord_redirect_uri = env['DISCORD_REDIRECT_URI']
    discord_client_id = env['DISCORD_CLIENT_ID']
    discord_client_secret = env['DISCORD_CLIENT_SECRET']
    jwt_secret_key = env['JWT_SECRET_KEY']

app = Flask(__name__)
app.config['MONGO_URI'] = connection_string
app.config["JWT_SECRET_KEY"] = jwt_secret_key

mongo = PyMongo(app).db
jwt = JWTManager(app)

@app.route("/api/users/version")
def version():
    return jsonify({
        "version": "1",
        "description": "This is the first API!"
    })

from .user import *
from .discord import *
from .profile import *

if __name__ == '__main__':
    app.run(debug=True)
