from flask import request, jsonify
from .app import mongo, app
from .identity import get_jwt_identity
from datetime import datetime
from bson import ObjectId
from bson.errors import InvalidId
from jsonschema import validate, ValidationError
import pymongo

profile_schema = {
    "type": "object",
    "properties": {
        "avatar": {"type": "string"},
        "description": {"type": "string", "maxLength": 100},
    },
    "required": []
}

def get_profile_of_user(user_id):
    profile = mongo.profiles.find_one(
        {"user_id": user_id},
        sort=[( 'updated_at', pymongo.DESCENDING )]
    )

    if not profile:
        return None

    profile["id"] = str(profile.pop("_id"))
    profile['user_id'] = str(profile['user_id'])
    return profile

def update_profile(profile):
    current_profile = get_profile_of_user(profile["user_id"])

    if current_profile:
        # Update the subset of the profile
        changed = False

        for key, new_value in profile.items():
            if 'id' not in key and current_profile.get(key) != new_value:
                current_profile[key] = new_value
                changed = True

        if not changed:
            # Profile has not changed, don't bother updating
            return current_profile

        profile = current_profile
        print('Current profile:', profile)

        if '_id' in profile:
            del profile['_id']

    profile["updated_at"] = datetime.utcnow()
    result = mongo.profiles.insert_one(profile)
    profile['id'] = str(result.inserted_id)
    profile['user_id'] = str(profile['user_id'])
    print('Returning profile:', profile)
    return profile

def populate_user(user):
    user_id = user.get("_id")

    if user_id:
        profile = get_profile_of_user(str(user_id))

        if profile:
            user["profile"] = profile

    user["id"] = str(user.pop("_id"))
    return user

@app.route('/api/users/<string:user_id>/profile', methods=['PUT', 'PATCH'])
def edit_profile(user_id):
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

    new_profile = {
        "user_id": str(user_id),
        "avatar": data.get("avatar"),
        "description": data.get("description")
    }

    for key in list(new_profile.keys()):
        if new_profile[key] is None:
            del new_profile[key]

    try:
        validate(instance=new_profile, schema=profile_schema)
    except ValidationError as e:
        return jsonify({"error": f"Validation error: {e.message}"}), 400

    profile = update_profile(new_profile)
    return jsonify(profile), 200