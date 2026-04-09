from flask import Blueprint, request, jsonify, session, make_response
from datetime import datetime, timezone, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import logging
from pymongo import MongoClient
import certifi
import os
from dotenv import load_dotenv
import jwt

load_dotenv()

# MongoDB setup
mongo_uri = os.getenv('MONGO_URI')
client = MongoClient(mongo_uri, tlsCAFile=certifi.where())
db = client['leadsPilotAI']

# MongoDB Collection
admin_users_collection = db['admin_users']  # Assuming you have 'db' already set up correctly as the client
clients_collection = db['clients']

logger = logging.getLogger(__name__)
logger.info(f"MongoDB URI in {__file__}: {mongo_uri}")

bp = Blueprint('admin_auth', __name__, url_prefix='/api/admin')

@bp.route("/login-with-token", methods=['POST'])
def login_with_token():
    data = request.get_json() or {}
    token = data.get('token')
    password = data.get('password')

    logger.info(f"Received token: {token}")


    if not token or not password:
        return jsonify({"error": "token and password are required"}), 400

    # Find user by token
    logger.info(f"querying admin collection: {admin_users_collection}")
    user = admin_users_collection.find_one({"invite_token": token})
    logger.info(f"Found user: {user}")
    if not user:
        return jsonify({"error": "Invalid invite token"}), 401

    if user['invite_token_expiry'] < datetime.utcnow():
        return jsonify({"error": "Invite token has expired"}), 401

    # Hash & save the new password
    hashed_password = generate_password_hash(password)
    update_result = admin_users_collection.update_one(
        {"_id": user['_id']},
        {"$set": {"password_hash": hashed_password, "invite_token": None, "invite_token_expiry": None}}
    )

    # Log the result of the update operation
    if update_result.modified_count == 0:
        logger.error(f"Failed to update password for user {user['_id']}. Update result: {update_result.raw_result}")
        return jsonify({"error": "Failed to update password. Please try again."}), 500

    # Retrieve client_slug from the associated Client document
    client = clients_collection.find_one({"_id": user['client_id']})
    if not client:
        return jsonify({"error": "Client not found"}), 404

    # Establish session
    session.clear()
    session["admin_user_id"] = str(user['_id'])
    session["admin_client_slug"] = client['slug']  # Retrieve client_slug from the Client document

    return jsonify({"success": True})



@bp.route('/login', methods=['POST', 'OPTIONS'])
def login():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response
        
    data = request.get_json() or {}
    email = data.get("email")
    password = data.get("password")

    logger.info(f"email: {email} password{password}")
    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    # Find user by email
    user = admin_users_collection.find_one({"email": email})

    if not user or not check_password_hash(user['password_hash'], password):
        return jsonify({"error": "Invalid email or password"}), 401
    
    # Fetch the associated client data (client_slug)
    client = clients_collection.find_one({"_id": user['client_id']})
    if not client:
        return jsonify({"error": "Client not found"}), 404
    
   # Generate JWT
    token = jwt.encode({
        'admin_user_id': str(user['_id']),
        'admin_client_slug': client['slug'],
        'exp': datetime.utcnow() + timedelta(hours=1)
    }, os.getenv('FLASK_SECRET_KEY'), algorithm='HS256')

    response = make_response(jsonify({"success": True, "token": token}))
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response

def create_response(data, status=200):
    response = make_response(jsonify(data), status)
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response


@bp.route('/verify-token', methods=['GET', 'OPTIONS'])
def verify_token():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Authorization'
        return response

    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return create_response({"error": "Missing or invalid token"}, 401)

    token = auth_header.split(' ')[1]
    try:
        payload = jwt.decode(token, os.getenv('FLASK_SECRET_KEY'), algorithms=['HS256'])
        logger.info(f"Token payload: {payload}")
        return create_response({"logged_in": True, "admin_user_id": payload['admin_user_id']})
    except jwt.ExpiredSignatureError:
        return create_response({"error": "Token expired"}, 401)
    except jwt.InvalidTokenError:
        return create_response({"error": "Invalid token"}, 401)

@bp.route('/logout', methods=['POST'])
def logout():
    """Logs out the current user by clearing the session."""
    session.clear()
    return jsonify({"success": True})
