from flask import Blueprint, request, jsonify, session, make_response
from datetime import datetime, timezone, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import logging
import os
import jwt
from bson import ObjectId
from core import admin_users_collection, clients_collection, db

logger = logging.getLogger(__name__)

bp = Blueprint('admin_auth', __name__, url_prefix='/api/admin')

# Super-admins (operators) may impersonate any client's admin dashboard for support.
# Bootstrap via env allowlist (comma-separated emails); a user with role="superadmin"
# in the DB also qualifies. Keep this list tight — these accounts can access every tenant.
SUPERADMIN_EMAILS = {e.strip().lower() for e in os.getenv("SUPERADMIN_EMAILS", "").split(",") if e.strip()}


def _decode_bearer_token():
    """Decode the caller's JWT from the Authorization header. Returns (payload, error)."""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None, (jsonify({"error": "Missing or invalid token"}), 401)
    try:
        token = auth_header.split(' ')[1]
        payload = jwt.decode(token, os.getenv('FLASK_SECRET_KEY'), algorithms=['HS256'])
        return payload, None
    except jwt.ExpiredSignatureError:
        return None, (jsonify({"error": "Token expired"}), 401)
    except jwt.InvalidTokenError:
        return None, (jsonify({"error": "Invalid token"}), 401)


def _is_superadmin(user) -> bool:
    if not user:
        return False
    if user.get('role') == 'superadmin':
        return True
    return (user.get('email') or '').lower() in SUPERADMIN_EMAILS

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
    try:
        user = admin_users_collection.find_one({"invite_token": token})
    except Exception as e:
        logger.error(f"Database error during login-with-token: {e}")
        return jsonify({"error": "Service temporarily unavailable"}), 503
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

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    # Find user by email
    try:
        user = admin_users_collection.find_one({"email": email})
    except Exception as e:
        logger.error(f"Database error during login: {e}")
        return jsonify({"error": "Service temporarily unavailable"}), 503

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
        return create_response({"logged_in": True, "admin_user_id": payload['admin_user_id'], "client_slug": payload.get('admin_client_slug')})
    except jwt.ExpiredSignatureError:
        return create_response({"error": "Token expired"}, 401)
    except jwt.InvalidTokenError:
        return create_response({"error": "Invalid token"}, 401)

@bp.route('/logout', methods=['POST'])
def logout():
    """Logs out the current user by clearing the session."""
    session.clear()
    return jsonify({"success": True})


@bp.route('/impersonate', methods=['POST'])
def impersonate():
    """Super-admin only: mint a short-lived JWT scoped to another client's dashboard.

    This is the audited, authenticated alternative to a 'backdoor': the caller must
    already be authenticated as a super-admin, the issued token is time-limited and
    tagged with who created it, and every use is written to an audit log.
    """
    payload, error = _decode_bearer_token()
    if error:
        return error

    # No chaining: you cannot launch an impersonation from within an impersonation.
    if payload.get('impersonated_by'):
        return jsonify({"error": "Cannot impersonate from an impersonation session"}), 403

    try:
        caller = admin_users_collection.find_one({"_id": ObjectId(payload.get('admin_user_id', ''))})
    except Exception:
        caller = None

    if not _is_superadmin(caller):
        logger.warning(f"Denied impersonation attempt by {payload.get('admin_user_id')} ({payload.get('admin_client_slug')})")
        return jsonify({"error": "Super-admin privileges required"}), 403

    target_slug = (request.get_json() or {}).get('client_slug')
    if not target_slug:
        return jsonify({"error": "client_slug is required"}), 400

    target_client = clients_collection.find_one({"slug": target_slug})
    if not target_client:
        return jsonify({"error": "Target client not found"}), 404

    now = datetime.now(timezone.utc)
    impersonation_token = jwt.encode({
        'admin_user_id': str(caller['_id']),
        'admin_client_slug': target_slug,
        'impersonated_by': str(caller['_id']),
        'impersonator_email': caller.get('email'),
        'exp': now + timedelta(minutes=30),  # shorter-lived than a normal session
    }, os.getenv('FLASK_SECRET_KEY'), algorithm='HS256')

    # Audit trail — who accessed which client, and when.
    try:
        db['impersonation_audit'].insert_one({
            'superadmin_user_id': caller['_id'],
            'superadmin_email': caller.get('email'),
            'target_client_slug': target_slug,
            'target_client_id': target_client['_id'],
            'action': 'impersonate',
            'created_at': now,
        })
    except Exception as e:
        logger.error(f"Failed to write impersonation audit log: {e}")

    logger.info(f"IMPERSONATION: {caller.get('email')} -> client '{target_slug}'")
    return create_response({
        "success": True,
        "token": impersonation_token,
        "client_slug": target_slug,
        "impersonating": True,
    })


@bp.route('/impersonation-audit', methods=['GET'])
def impersonation_audit():
    """Super-admin only: view the recent impersonation audit log."""
    payload, error = _decode_bearer_token()
    if error:
        return error
    try:
        caller = admin_users_collection.find_one({"_id": ObjectId(payload.get('admin_user_id', ''))})
    except Exception:
        caller = None
    if not _is_superadmin(caller):
        return jsonify({"error": "Super-admin privileges required"}), 403

    entries = list(db['impersonation_audit'].find().sort("created_at", -1).limit(100))
    for e in entries:
        e['_id'] = str(e['_id'])
        e['superadmin_user_id'] = str(e.get('superadmin_user_id'))
        e['target_client_id'] = str(e.get('target_client_id'))
        if e.get('created_at'):
            e['created_at'] = e['created_at'].isoformat()
    return create_response({"entries": entries})
