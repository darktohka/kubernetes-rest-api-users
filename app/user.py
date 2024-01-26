from flask import request, jsonify, session
from bson import ObjectId
from bson.errors import InvalidId
from jsonschema import validate, ValidationError
from .identity import get_jwt_identity, rotate_jwt
from .kafka import create_producer, register_kafka_listener
from .app import app, mongo
from .profile import populate_user

USER_DELETED_TOPIC = 'user-deleted'
POPULATE_USERS_TOPIC = 'populate-users'
USERS_POPULATED_TOPIC = 'users-populated'

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
    new_user["id"] = str(result.inserted_id)
    return jsonify(new_user), 201

@app.route('/api/users/<string:user_id>', methods=['PUT', 'PATCH'])
def edit_user(user_id):
    try:
        user_id = ObjectId(user_id)
    except InvalidId:
        return jsonify({"error": "Invalid user ID"}), 400

    user = mongo.users.find_one({"_id": user_id})

    if not user:
        return jsonify({"error": "User not found"}), 404

    # Ensure the user has permission
    try:
        current_user = get_jwt_identity()
    except:
        return jsonify({'error': 'Not logged in'}), 401

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
    user["id"] = str(user.pop("_id"))
    return jsonify(user)

@app.route('/api/users/<string:user_id>', methods=['DELETE'])
def delete_user(user_id):
    try:
        user_id = ObjectId(user_id)
    except InvalidId:
        return jsonify({"error": "Invalid user ID"}), 400

    user = mongo.users.find_one({"_id": user_id})

    if not user:
        return jsonify({"error": "User not found"}), 404

    # Ensure the user has permission
    try:
        current_user = get_jwt_identity()
    except:
        return jsonify({'error': 'Not logged in'}), 401

    if current_user['id'] != str(user['_id']) and 'admin' not in current_user['roles']:
        return jsonify({"error": "You cannot edit this user's profile"}), 403

    mongo.users.delete_one({"_id": user_id})
    user_deleted(str(user_id))
    rotate_jwt()
    return jsonify({"message": "User deleted"}), 200

@app.route("/api/users/logout")
def logout():
    session.clear()
    return jsonify({"message": "Logged out"}), 200

producer = create_producer()

def user_deleted(user_id):
    producer.send(USER_DELETED_TOPIC, {'id': user_id})
    producer.flush()

def on_populate_users(message):
    data = message.value
    userIds = data['userIds']
    users = mongo.users.find({'_id': {'$in': userIds}})
    users = [populate_user(user) for user in users]

    print('Sending populated users:', users)
    producer.send(USERS_POPULATED_TOPIC, {'users': users})
    producer.flush()

register_kafka_listener(POPULATE_USERS_TOPIC, enable_auto_commit=True, auto_offset_reset='latest', listener=on_populate_users)
