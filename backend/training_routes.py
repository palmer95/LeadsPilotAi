# training_routes.py
from flask import Blueprint, request, jsonify
import jwt
import os
from bson import ObjectId

# Import the database object from our core file
from core import db

bp = Blueprint('training_routes', __name__, url_prefix='/api/admin/training')
flask_secret_key = os.getenv('FLASK_SECRET_KEY')
training_collection = db['custom_training'] # Our new collection

# This helper will be used in all routes to get the authenticated client
def get_client_slug_from_token():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None, (jsonify({"error": "Missing or invalid token"}), 401)
    try:
        token = auth_header.split(' ')[1]
        payload = jwt.decode(token, flask_secret_key, algorithms=['HS256'])
        client_slug = payload.get('admin_client_slug')
        if not client_slug:
            return None, (jsonify({"error": "Invalid token payload"}), 401)
        return client_slug, None
    except Exception as e:
        return None, (jsonify({"error": f"Invalid or expired token: {e}"}), 401)

@bp.route('/', methods=['GET'])
def get_training_data():
    client_slug, error = get_client_slug_from_token()
    if error:
        return error
    
    try:
        # Find all training data for the specific client
        data = list(training_collection.find({"client_slug": client_slug}))
        # Convert ObjectId to string for JSON serialization
        for item in data:
            item['_id'] = str(item['_id'])
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": f"Database error: {e}"}), 500

@bp.route('/', methods=['POST'])
def add_training_data():
    client_slug, error = get_client_slug_from_token()
    if error:
        return error

    data = request.get_json()
    question = data.get('question')
    answer = data.get('answer')

    if not question or not answer:
        return jsonify({"error": "Question and answer are required"}), 400

    new_entry = {
        "client_slug": client_slug,
        "question": question,
        "answer": answer
    }
    result = training_collection.insert_one(new_entry)
    new_entry['_id'] = str(result.inserted_id)
    
    return jsonify(new_entry), 201

@bp.route('/<item_id>', methods=['DELETE'])
def delete_training_data(item_id):
    client_slug, error = get_client_slug_from_token()
    if error:
        return error
    
    # Ensure the client is only deleting their own data
    result = training_collection.delete_one({
        "_id": ObjectId(item_id),
        "client_slug": client_slug
    })

    if result.deleted_count == 1:
        return jsonify({"success": True}), 200
    else:
        return jsonify({"error": "Item not found or you do not have permission to delete it"}), 404