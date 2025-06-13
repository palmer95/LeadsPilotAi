from flask import Blueprint, request, jsonify, make_response
from pymongo import MongoClient
from bson import ObjectId
from flask_cors import CORS
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
    response = make_response(jsonify(data), status)
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response

@bp.route('/leads', methods=['GET', 'OPTIONS'])
def get_leads():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Authorization'
        return response

    logger.info(f"Request headers: {dict(request.headers)}")
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        logger.error("Missing or invalid Authorization header")
        return create_response({"error": "Missing or invalid token"}, 401)

    token = auth_header.split(' ')[1]
    try:
        payload = jwt.decode(token, os.getenv('FLASK_SECRET_KEY'), algorithms=['HS256'])
        client_slug = payload.get('admin_client_slug')
        if not client_slug:
            logger.error("Invalid token payload")
            return create_response({"error": "Invalid token"}, 401)
        logger.info(f"Token payload: {payload}")
    except jwt.ExpiredSignatureError:
        logger.error("Token expired")
        return create_response({"error": "Token expired"}, 401)
    except jwt.InvalidTokenError:
        logger.error("Invalid token")
        return create_response({"error": "Invalid token"}, 401)

    leads = list(leads_collection.find({"client_slug": client_slug}))
    return create_response([lead for lead in leads])

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
