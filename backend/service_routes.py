# services_routes.py
from flask import Blueprint, request, jsonify
import jwt
import os
from bson import ObjectId
from uuid import uuid4

# Import the database object from our core file
from core import db, clients_collection

bp = Blueprint('services_routes', __name__, url_prefix='/api/admin/services')
flask_secret_key = os.getenv('FLASK_SECRET_KEY')

# --- Helper function for secure authentication ---
def get_client_id_from_token():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None, (jsonify({"error": "Missing or invalid token"}), 401)
    try:
        token = auth_header.split(' ')[1]
        payload = jwt.decode(token, flask_secret_key, algorithms=['HS256'])
        client_id_str = payload.get('client_id')
        if not client_id_str:
            return None, (jsonify({"error": "Invalid token payload"}), 401)
        return ObjectId(client_id_str), None
    except Exception as e:
        return None, (jsonify({"error": f"Invalid or expired token: {e}"}), 401)

# --- API Endpoints ---

# GET all services for a client
@bp.route('/', methods=['GET'])
def get_services():
    client_id, error = get_client_id_from_token()
    if error:
        return error
    
    client = clients_collection.find_one({"_id": client_id})
    if not client:
        return jsonify({"error": "Client not found"}), 404
        
    # Return the services array, or an empty array if it doesn't exist
    return jsonify(client.get("services", []))

# POST a new service for a client
@bp.route('/', methods=['POST'])
def add_service():
    client_id, error = get_client_id_from_token()
    if error:
        return error

    data = request.get_json()
    if not data or not data.get('name') or not data.get('duration') or not data.get('price'):
        return jsonify({"error": "Missing required fields: name, duration, price"}), 400

    new_service = {
        "_id": ObjectId(), # Generate a unique ID for the service
        "name": data['name'],
        "description": data.get('description', ''),
        "duration": data['duration'],
        "price": data['price']
    }

    # Use MongoDB's $push operator to add the new service to the array
    result = clients_collection.update_one(
        {"_id": client_id},
        {"$push": {"services": new_service}}
    )

    if result.modified_count == 1:
        # Convert ObjectId to string for the JSON response
        new_service['_id'] = str(new_service['_id'])
        return jsonify(new_service), 201
    else:
        return jsonify({"error": "Could not add service"}), 500

# DELETE a specific service from a client's list
@bp.route('/<service_id>', methods=['DELETE'])
def delete_service(service_id):
    client_id, error = get_client_id_from_token()
    if error:
        return error
        
    try:
        service_obj_id = ObjectId(service_id)
    except Exception:
        return jsonify({"error": "Invalid service ID format"}), 400

    # Use MongoDB's $pull operator to remove the specific service from the array
    result = clients_collection.update_one(
        {"_id": client_id},
        {"$pull": {"services": {"_id": service_obj_id}}}
    )

    if result.modified_count == 1:
        return jsonify({"success": True}), 200
    else:
        return jsonify({"error": "Service not found or could not be deleted"}), 404

# PUT (Update) a specific service
@bp.route('/<service_id>', methods=['PUT'])
def update_service(service_id):
    client_id, error = get_client_id_from_token()
    if error:
        return error
    
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is empty"}), 400

    try:
        service_obj_id = ObjectId(service_id)
    except Exception:
        return jsonify({"error": "Invalid service ID format"}), 400

    # Create the update object with only the fields provided in the request
    update_fields = {}
    for key in ['name', 'description', 'duration', 'price']:
        if key in data:
            update_fields[f"services.$.{key}"] = data[key]

    if not update_fields:
        return jsonify({"error": "No valid fields to update"}), 400

    # Use the positional '$' operator to update the correct element in the array
    result = clients_collection.update_one(
        {"_id": client_id, "services._id": service_obj_id},
        {"$set": update_fields}
    )

    if result.modified_count == 1:
        return jsonify({"success": True}), 200
    else:
        return jsonify({"error": "Service not found or could not be updated"}), 404