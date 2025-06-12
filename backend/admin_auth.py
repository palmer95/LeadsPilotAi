from flask import Blueprint, request, jsonify, session, make_response
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
import logging
from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

# MongoDB setup
mongo_uri = os.getenv('MONGO_URI')
client = MongoClient(mongo_uri)
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



@bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    # Find user by email
    user = admin_users_collection.find_one({"email": email})

    if not user:
        return jsonify({"error": "Invalid email or password"}), 401
    
    # Check if the provided password matches the stored hash
    if not check_password_hash(user['password_hash'], password):
        return jsonify({"error": "Invalid email or password"}), 401

    # Fetch the associated client data (client_slug)
    client = clients_collection.find_one({"_id": user['client_id']})
    if not client:
        return jsonify({"error": "Client not found"}), 404
    
    # 1) Establish session
    session.clear()
    session.permanent = True
    session["admin_user_id"] = str(user['_id'])
    session["admin_client_slug"] = client['slug']  # Assuming client_slug is stored during onboarding

    logger.info(f"Session set after login: {session}")
    logger.info(f"Response cookies: {request.cookies}")  # Cookies should be empty here
    
    response = make_response(jsonify({"success": True}))
    logger.info(f"Response headers: {response.headers}")
    return response


@bp.route('/check-session', methods=['GET', 'OPTIONS'])
def check_session():
    if request.method == 'OPTIONS':
        logger.info("Handling OPTIONS for check-session")
        response = make_response()
        response.headers['Access-Control-Allow-Origin'] = request.headers.get('Origin', 'https://leadspilotai.com')
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        return response

    logger.info(f"Request URL: {request.url}")
    logger.info(f"Request headers: {dict(request.headers)}")
    logger.info(f"Request cookies: {request.cookies}")
    logger.info(f"Session in check-session: {session}")
    if "admin_user_id" in session:
        logger.info("Session found, returning logged_in: True")
        response = jsonify({"logged_in": True})
        response.headers['Access-Control-Allow-Origin'] = request.headers.get('Origin', 'https://leadspilotai.com')
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response
    logger.error("No session found, returning logged_in: False")
    response = jsonify({"error": "No session found"}, status=401)
    response.headers['Access-Control-Allow-Origin'] = request.headers.get('Origin', 'https://leadspilotai.com')
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    return response, 401


@bp.route('/logout', methods=['POST'])
def logout():
    """Logs out the current user by clearing the session."""
    session.clear()
    return jsonify({"success": True})
