from flask import request, jsonify, redirect
from urllib.parse import urlencode
import requests
import hashlib

from .app import discord_client_id, discord_client_secret, discord_redirect_uri, mongo, app
from .profile import populate_user, update_profile
from .identity import create_jwt

scope = 'guilds identify email'

def create_client_id(request):
    client_ip = request.remote_addr
    user_agent = request.headers.get("User-Agent", "Unknown")

    client_id = hashlib.sha256(f"{client_ip}{user_agent}".encode("utf-8")).hexdigest()
    return client_id

def lookup_with_token(link, access_token):
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Bearer {access_token}",
    }

    response = requests.get(link, headers=headers)

    if not response.ok:
        raise Exception("Response not ok: " + response.text)

    return response.json()

def exchange_code(code):
    data = {
        "client_id": discord_client_id,
        "client_secret": discord_client_secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": discord_redirect_uri,
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
    }

    url = "https://discord.com/api/oauth2/token"

    response = requests.post(url, data=data, headers=headers)

    if not response.ok:
        raise Exception("Response not ok: " + response.text)

    return response.json()

def lookup_myself(access_token):
    link = "https://discord.com/api/v10/users/@me"
    return lookup_with_token(link, access_token)

@app.route("/api/users/discord/login")
def redirect_to_discord():
    client_id = create_client_id(request)

    parameters = urlencode({
        "scope": scope,
        "state": client_id,
        "response_type": "code",
        "approval_prompt": "auto",
        "redirect_uri": discord_redirect_uri,
        "client_id": discord_client_id,
    })

    auth_url = f"https://discord.com/oauth2/authorize?{parameters}"
    return redirect(auth_url, code=302)

@app.route("/api/users/discord/callback")
def create():
    code = request.args.get("code")
    state = request.args.get("state")

    if state != create_client_id(request):
        return jsonify({"ok": False, "error": "Invalid state!"}), 400

    try:
        token = exchange_code(code)
    except Exception as error:
        print(error)
        return jsonify({"ok": False, "error": "Discord authentication failed!"}), 500

    access_token = token["access_token"]

    try:
        profile = lookup_myself(access_token)
    except Exception as error:
        print(error)
        return jsonify({"ok": False, "error": "Discord lookup failed!"}), 500

    discord_id = profile["id"]
    username = profile["username"]
    email = profile["email"]
    avatar = profile["avatar"]

    new_user = {
        "discord_id": discord_id,
        "username": username,
        "email": email,
        "roles": ["user"]
    }

    user = mongo.users.find_one({"email": new_user["email"]})

    if not user:
        user = mongo.users.find_one({"username": new_user["username"]})

    if not user:
        user = mongo.users.insert_one(new_user)
        new_user['_id'] = user.inserted_id
        user = new_user

    # Update profile with new discord avatar
    new_profile = {
        "user_id":  str(user['_id']),
        "avatar": f"https://cdn.discordapp.com/avatars/{discord_id}/{avatar}.png"
    }

    update_profile(new_profile)

    user = populate_user(user)
    access_token = create_jwt(user)
    result = {'user': user, 'token': access_token, 'ok': True}
    return jsonify(result), 200
