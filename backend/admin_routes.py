from flask import Blueprint, request, jsonify, session
from pymongo import MongoClient
from bson import ObjectId
from flask_cors import CORS
import os
from dotenv import load_dotenv

load_dotenv()

# MongoDB setup
mongo_uri = os.getenv('MONGO_URI')
client = MongoClient(mongo_uri)
db = client['leadsPilotAI']

# MongoDB Collections
leads_collection = db.leads
faqs_collection = db.faqs
admin_users_collection = db.admin_users

bp = Blueprint('admin_routes', __name__, url_prefix='/api/admin/data')

# Route to get leads
@bp.route('/leads', methods=['GET'])
def get_leads():
    # Query MongoDB to fetch all leads for a client
    leads = list(leads_collection.find())  # Returns a cursor, so we convert it to a list
    result = [
        {"id": str(lead["_id"]), "name": lead["name"], "email/phone": lead["email"]}
        for lead in leads
    ]
    return jsonify(result), 200

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
