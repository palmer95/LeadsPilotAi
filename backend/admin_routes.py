# backend/admin_routes.py
from flask import Blueprint, request, jsonify, session
from db import SessionLocal, Lead, FAQ, AdminUser
from flask_cors import CORS
from werkzeug.security import check_password_hash


bp = Blueprint('admin_routes', __name__, url_prefix='/api/admin')

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

# backend/admin_auth.py

@bp.route('/logout', methods=['POST'])
def logout():
    """Logs out the current user by clearing the session."""
    session.clear()
    return jsonify({"success": True})


@bp.route('/leads', methods=['GET'])
def get_leads():
    db = SessionLocal()
    leads = db.query(Lead).all()
    result = [{"id": lead.id, "name": lead.name, "email/phone": lead.email} for lead in leads]
    return jsonify(result), 200

@bp.route('/faqs', methods=['GET'])
def get_faqs():
    db = SessionLocal()
    faqs = db.query(FAQ).all()
    result = [{"id": faq.id, "question": faq.question, "answer": faq.answer} for faq in faqs]
    return jsonify(result), 200