# backend/admin_auth.py

from flask import Blueprint, request, jsonify, session
from datetime import datetime, timezone
from db import SessionLocal, AdminUser
from werkzeug.security import generate_password_hash, check_password_hash

bp = Blueprint('admin_auth', __name__, url_prefix='/api/admin')

@bp.route('/login-with-token', methods=['POST'])
def login_with_token():
    data = request.get_json() or {}
    token    = data.get('token')
    password = data.get('password')

    if not token or not password:
        return jsonify({"error": "token and password are required"}), 400

    db = SessionLocal()
    user = db.query(AdminUser).filter_by(invite_token=token).first()
    if not user:
        return jsonify({"error": "Invalid invite token"}), 401

    if user.invite_token_expiry < datetime.utcnow():
        return jsonify({"error": "Invite token has expired"}), 401

    # 1) Hash & save the new password
    user.password_hash        = generate_password_hash(password)
    user.invite_token         = None
    user.invite_token_expiry  = None
    db.commit()

    # 2) Establish their session
    session.clear()
    session["admin_user_id"]     = user.id
    session["admin_client_slug"] = user.client.slug

    return jsonify({"success": True})

@bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    db = SessionLocal()
    user = db.query(AdminUser).filter_by(email=email).first()

    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "Invalid email or password"}), 401

    # 1) Establish session
    session.clear()
    session["admin_user_id"] = user.id
    session["admin_client_slug"] = user.client.slug

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

