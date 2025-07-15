# admin_routes.py (Cleaned up and corrected)

from flask import Blueprint, request, jsonify
from pymongo import MongoClient
import os
import jwt
import logging

# Setup - assuming these are correctly configured
logger = logging.getLogger(__name__)
mongo_uri = os.getenv('MONGO_URI')
flask_secret_key = os.getenv('FLASK_SECRET_KEY')

client = MongoClient(mongo_uri)
db = client['leadsPilotAI']
leads_collection = db.leads
faqs_collection = db.faqs

bp = Blueprint('admin_routes', __name__, url_prefix='/api/admin/data')


@bp.route('/leads', methods=['GET'])
def get_leads():
    # 1. Authentication
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({"error": "Missing or invalid token"}), 401

    try:
        token = auth_header.split(' ')[1]
        payload = jwt.decode(token, flask_secret_key, algorithms=['HS256'])
        client_slug = payload.get('admin_client_slug')
        if not client_slug:
            return jsonify({"error": "Invalid token payload"}), 401
    except Exception as e:
        logger.error(f"Token decoding error: {e}")
        return jsonify({"error": "Invalid or expired token"}), 401

    # 2. Database Query
    try:
        leads_cursor = leads_collection.find({"company_slug": client_slug}).sort("created_at", -1)
        
        # 3. Data Serialization (The Fix)
        # Convert MongoDB documents (with ObjectId) to a JSON-serializable list of dicts
        serializable_leads = []
        for lead in leads_cursor:
            lead['_id'] = str(lead['_id']) # Convert ObjectId to string
            # You can also format dates here if needed, e.g., lead['created_at'] = lead['created_at'].isoformat()
            serializable_leads.append(lead)
            
        return jsonify(serializable_leads)
        
    except Exception as e:
        logger.error(f"Database error in get_leads for {client_slug}: {e}")
        return jsonify({"error": "An internal error occurred while fetching leads."}), 500


@bp.route('/faqs', methods=['GET'])
def get_faqs():
    # 1. Authentication (Added for security)
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({"error": "Missing or invalid token"}), 401

    try:
        token = auth_header.split(' ')[1]
        payload = jwt.decode(token, flask_secret_key, algorithms=['HS256'])
        client_slug = payload.get('admin_client_slug')
        if not client_slug:
            return jsonify({"error": "Invalid token payload"}), 401
    except Exception as e:
        logger.error(f"Token decoding error: {e}")
        return jsonify({"error": "Invalid or expired token"}), 401

    # 2. Database Query (Now correctly scoped to the client)
    try:
        faqs_cursor = faqs_collection.find({"company_slug": client_slug})
        
        # 3. Data Serialization
        serializable_faqs = []
        for faq in faqs_cursor:
            faq['_id'] = str(faq['_id'])
            serializable_faqs.append(faq)
            
        return jsonify(serializable_faqs)
        
    except Exception as e:
        logger.error(f"Database error in get_faqs for {client_slug}: {e}")
        return jsonify({"error": "An internal error occurred while fetching FAQs."}), 500