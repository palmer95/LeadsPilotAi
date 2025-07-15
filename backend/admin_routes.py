from flask import Blueprint, request, jsonify, make_response
from pymongo import MongoClient
from bson import ObjectId, json_util
from flask_cors import CORS
import json
import os
from dotenv import load_dotenv
import logging
import jwt

load_dotenv()

# MongoDB setup
mongo_uri = os.getenv('MONGO_URI')
client = MongoClient(mongo_uri)
db = client['leadsPilotAI']

# MongoDB Collections
leads_collection = db.leads
faqs_collection = db.faqs
admin_users_collection = db.admin_users

logger = logging.getLogger(__name__)
bp = Blueprint('admin_routes', __name__, url_prefix='/api/admin/data')

def create_response(data, status=200):
    # A helper to correctly format JSON responses from MongoDB data
    return Response(
        json.dumps(data, default=json_util.default),
        mimetype="application/json",
        status=status
    )

@bp.route('/leads', methods=['GET', 'OPTIONS'])
def get_leads():
    if request.method == 'OPTIONS':
        # ... (OPTIONS handling is fine) ...
        response = make_response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Authorization'
        return response

    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return create_response({"error": "Missing or invalid token"}, 401)

    try:
        token = auth_header.split(' ')[1]
        payload = jwt.decode(token, os.getenv('FLASK_SECRET_KEY'), algorithms=['HS256'])
        # The key in the JWT payload is 'admin_client_slug', which is correct
        client_slug = payload.get('admin_client_slug')
        if not client_slug:
            return create_response({"error": "Invalid token payload"}, 401)
    except Exception as e:
        logger.error(f"Token decoding error: {e}")
        return create_response({"error": "Invalid or expired token"}, 401)

    # 1. Query using 'company_slug' to match what's in the database
    # 2. Sort by 'created_at' in descending order to get the most recent leads first
    leads = list(leads_collection.find({"company_slug": client_slug}).sort("created_at", -1))
    
    # Use our helper to correctly format the response, handling MongoDB's ObjectId
    return create_response(leads)

# Route to get FAQs
@bp.route('/faqs', methods=['GET'])
def get_faqs():
    # Query MongoDB to fetch all FAQs for a client
    faqs = list(faqs_collection.find())  # Returns a cursor, so we convert it to a list
    result = [
        {"id": str(faq["_id"]), "question": faq["question"], "answer": faq["answer"]}
        for faq in faqs
    ]
    return jsonify(result), 200
