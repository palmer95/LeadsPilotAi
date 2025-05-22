from flask import Blueprint, request, jsonify, session
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
admin_users_collection = db.admin_users

logger = logging.getLogger(__name__)
logger.info(f"MongoDB URI in {__file__}: {mongo_uri}")

bp = Blueprint('admin_auth', __name__, url_prefix='/api/admin')

@bp.route("/login-with-token", methods=['POST'])
def login_with_token():
    data = request.get_json() or {}
    token = data.get('token')
    password = data.get('password')

    if not token or not password:
        return jsonify({"error": "token and password are required"}), 400

    # Find user by token
    user = admin_users_collection.find_one({"invite_token": token})
    if not user:
        return jsonify({"error": "Invalid invite token"}), 401

    if user['invite_token_expiry'] < datetime.utcnow():
        return jsonify({"error": "Invite token has expired"}), 401

    # Hash & save the new password
    hashed_password = generate_password_hash(password)
    admin_users_collection.update_one(
        {"_id": user['_id']},
        {"$set": {"password_hash": hashed_password, "invite_token": None, "invite_token_expiry": None}}
    )

    # Establish session
    session.clear()
    session["admin_user_id"] = str(user['_id'])
    session["admin_client_slug"] = user['client_slug']  # Assume client_slug is stored during onboarding

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

    # 1) Establish session
    session.clear()
    session.permanent = True
    session["admin_user_id"] = str(user['_id'])
    session["admin_client_slug"] = user['client_slug']  # Assuming client_slug is stored during onboarding

    return jsonify({"success": True})


@bp.route('/check-session', methods=['GET'])
def check_session():
    """Checks if the user is logged in via session."""
    if "admin_user_id" in session:
        return jsonify({"logged_in": True})
    return jsonify({"logged_in": False}), 401

@bp.route('/logout', methods=['POST'])
def logout():
    """Logs out the current user by clearing the session."""
    session.clear()
    return jsonify({"success": True})
