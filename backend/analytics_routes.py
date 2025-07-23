# analytics_routes.py
from flask import Blueprint, jsonify, request
import jwt
import os
from bson import ObjectId

# Import the database object from our core file
from core import db, conversations_collection, leads_collection

bp = Blueprint('analytics_routes', __name__, url_prefix='/api/admin/analytics')
flask_secret_key = os.getenv('FLASK_SECRET_KEY')

@bp.route('/', methods=['GET'])
def get_analytics_data():
    # Authentication to get the client_id
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({"error": "Missing or invalid token"}), 401
    try:
        token = auth_header.split(' ')[1]
        payload = jwt.decode(token, flask_secret_key, algorithms=['HS256'])
        client_id_str = payload.get('client_id')
        if not client_id_str:
            return jsonify({"error": "Invalid token payload"}), 401
        client_id = ObjectId(client_id_str)
    except Exception as e:
        return jsonify({"error": f"Invalid or expired token: {e}"}), 401

    try:
        # --- GATHER ALL ANALYTICS DATA ---
        
        # 1. Get total lead count
        lead_count = leads_collection.count_documents({"client_id": client_id})

        # 2. Get total conversation count
        # We'll need to add a client_id to conversation documents for this to be accurate.
        # For now, let's use the slug from the client document.
        client_doc = db['clients'].find_one({"_id": client_id})
        client_slug = client_doc.get('slug') if client_doc else None

        conversation_count = 0
        recent_conversations = []
        if client_slug:
            conversation_count = conversations_collection.count_documents({"company": client_slug})
            # 3. Get the 5 most recent conversations
            recent_conversations_cursor = conversations_collection.find(
                {"company": client_slug},
                {"messages": 1} # Only get the messages field
            ).sort("messages.timestamp", -1).limit(5)
            
            for conv in recent_conversations_cursor:
                conv['_id'] = str(conv['_id'])
                recent_conversations.append(conv)

        # 4. Assemble the response payload
        analytics_payload = {
            "stats": {
                "leadCount": lead_count,
                "conversationCount": conversation_count,
                "appointmentsBooked": 0 # Placeholder for now
            },
            "recentConversations": recent_conversations
        }
        
        return jsonify(analytics_payload)

    except Exception as e:
        return jsonify({"error": f"An error occurred while fetching analytics: {e}"}), 500