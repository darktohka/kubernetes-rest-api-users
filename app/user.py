from flask import request, jsonify, session
from bson import ObjectId
from bson.errors import InvalidId
from jsonschema import validate, ValidationError
from flask_jwt_extended import jwt_required, get_jwt_identity

from .app import app, mongo, jwt
from .profile import populate_user

user_schema = {
    "type": "object",
    "properties": {
        "discord_id": {"type": "string", "minLength": 1},
        "username": {"type": "string", "minLength": 1},
        "email": {"type": "string", "format": "email"},
        "roles": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["username", "email"]
}

@app.route('/api/users', methods=['GET'])
def get_all_users():
    users = mongo.users.find()
    user_list = []

    for user in users:
        user = populate_user(user)
        user_list.append(user)

    return jsonify(user_list)

@app.route('/api/users/<string:user_id>', methods=['GET'])
def get_user(user_id):
    try:
        user_id = ObjectId(user_id)
    except InvalidId:
        return jsonify({"error": "Invalid user ID"}), 400

    user = mongo.users.find_one({"_id": user_id})

    if user:
        user = populate_user(user)
        return jsonify(user)

    return jsonify({"error": "User not found"}), 404

@app.route('/api/users', methods=['POST'])
def create_user():
    data = request.json

    new_user = {
        "username": data.get("username"),
        "email": data.get("email"),
        "roles": data.get("roles", [])
    }

    try:
        validate(instance=new_user, schema=user_schema)
    except ValidationError as e:
        return jsonify({"error": f"Validation error: {e.message}"}), 400

    if mongo.users.find_one({"email": new_user["email"]}):
        return jsonify({"error": "User with email already exists"}), 400

    if mongo.users.find_one({"username": new_user["username"]}):
        return jsonify({"error": "User with username already exists"}), 400

    result = mongo.users.insert_one(new_user)
    new_user["_id"] = str(result.inserted_id)
    return jsonify(new_user), 201

@app.route('/api/users/<string:user_id>', methods=['PUT', 'PATCH'])
@jwt_required()
def edit_user(user_id):
    try:
        user_id = ObjectId(user_id)
    except InvalidId:
        return jsonify({"error": "Invalid user ID"}), 400

    user = mongo.users.find_one({"_id": user_id})

    if not user:
        return jsonify({"error": "User not found"}), 404

    # Ensure the user has permission
    current_user = get_jwt_identity()

    if current_user['id'] != str(user['_id']) and 'admin' not in current_user['roles']:
        return jsonify({"error": "You cannot edit this user's profile"}), 403

    data = request.json
    new_user = {
        "username": data.get("username", user["username"]),
        "email": data.get("email", user["email"]),
        "roles": data.get("roles", user["roles"])
    }
    new_values = {
        "$set": new_user
    }

    if user["email"] != new_user["email"] and mongo.users.find_one({"email": new_user["email"]}):
        return jsonify({"error": "User with email already exists"}), 400

    if user["username"] != new_user["username"] and mongo.users.find_one({"username": new_user["username"]}):
        return jsonify({"error": "User with username already exists"}), 400

    mongo.users.update_one({"_id": user_id}, new_values)
    user = mongo.users.find_one({"_id": user_id})
    user["_id"] = str(user["_id"])
    return jsonify(user)

@app.route('/api/users/<string:user_id>', methods=['DELETE'])
@jwt_required()
def delete_user(user_id):
    try:
        user_id = ObjectId(user_id)
    except InvalidId:
        return jsonify({"error": "Invalid user ID"}), 400

    user = mongo.users.find_one({"_id": user_id})

    if not user:
        return jsonify({"error": "User not found"}), 404

    # Ensure the user has permission
    current_user = get_jwt_identity()

    if current_user['id'] != str(user['_id']) and 'admin' not in current_user['roles']:
        return jsonify({"error": "You cannot edit this user's profile"}), 403

    mongo.users.delete_one({"_id": user_id})
    return jsonify({"message": "User deleted"}), 200

@app.route("/api/users/logout")
def logout():
    session.clear()
    return jsonify({"message": "Logged out"}), 200