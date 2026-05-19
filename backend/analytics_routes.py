# analytics_routes.py
from flask import Blueprint, jsonify, request
import jwt
import os
import logging
from core import conversations_collection, leads_collection

bp = Blueprint('analytics_routes', __name__, url_prefix='/api/admin/analytics')
flask_secret_key = os.getenv('FLASK_SECRET_KEY')
logger = logging.getLogger(__name__)

FALLBACK_PHRASES = ["don't have that specific detail", "contact the team directly"]


@bp.route('/', methods=['GET'])
def get_analytics_data():
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
        return jsonify({"error": f"Invalid or expired token: {e}"}), 401

    try:
        lead_count = leads_collection.count_documents({"company_slug": client_slug})
        conversation_count = conversations_collection.count_documents({"company": client_slug})

        all_conversations = list(
            conversations_collection.find(
                {"company": client_slug},
                {"session_id": 1, "messages": 1}
            ).sort("_id", -1)
        )

        all_questions = []
        knowledge_gaps = []
        total_messages = 0

        for conv in all_conversations:
            for msg in conv.get("messages", []):
                user_q = msg.get("user", "").strip()
                bot_r = msg.get("bot", "").strip()
                ts = msg.get("timestamp")
                ts_str = ts.isoformat() if ts else None

                if user_q:
                    total_messages += 1
                    all_questions.append({"question": user_q, "timestamp": ts_str})
                    if any(phrase in bot_r.lower() for phrase in FALLBACK_PHRASES):
                        knowledge_gaps.append({
                            "question": user_q,
                            "botResponse": bot_r,
                            "timestamp": ts_str
                        })

        recent_conversations = []
        for conv in all_conversations[:15]:
            messages = conv.get("messages", [])
            last_ts = next(
                (m["timestamp"].isoformat() for m in reversed(messages) if m.get("timestamp")),
                None
            )
            recent_conversations.append({
                "_id": str(conv["_id"]),
                "session_id": conv.get("session_id", ""),
                "messageCount": len(messages),
                "lastActive": last_ts,
                "messages": [
                    {
                        "user": m.get("user", ""),
                        "bot": m.get("bot", ""),
                        "timestamp": m["timestamp"].isoformat() if m.get("timestamp") else None,
                    }
                    for m in messages
                ],
            })

        return jsonify({
            "stats": {
                "conversationCount": conversation_count,
                "messageCount": total_messages,
                "leadCount": lead_count,
                "gapCount": len(knowledge_gaps),
            },
            "recentConversations": recent_conversations,
            "allQuestions": all_questions,
            "knowledgeGaps": knowledge_gaps,
        })

    except Exception as e:
        logger.error(f"Analytics error for {client_slug}: {e}")
        return jsonify({"error": f"An error occurred: {e}"}), 500
