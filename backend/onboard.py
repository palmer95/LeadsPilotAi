import os
import secrets
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage
from flask import Blueprint, request, jsonify
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv

load_dotenv()

# MongoDB setup
mongo_uri = os.getenv('MONGO_URI')
client = MongoClient(mongo_uri)
db = client['leadsPilotAI']

clients_collection = db.clients
admin_users_collection = db.admin_users
faqs_collection = db.faqs

bp = Blueprint('onboard', __name__, url_prefix='/api')

def send_invite_email(company_name: str, invite_link: str, to_email: str):
    print('About to email: ', to_email, ' for company: ', company_name, '.\n\nWith invite link: ', invite_link)
    SMTP_SERVER = os.getenv("SMTP_SERVER")
    SMTP_PORT   = int(os.getenv("SMTP_PORT", 465))
    SMTP_USER   = os.getenv("SMTP_USER")
    SMTP_PASS   = os.getenv("SMTP_PASS")
    FROM_EMAIL  = os.getenv("FROM_EMAIL", SMTP_USER)

    if not (SMTP_SERVER and SMTP_USER and SMTP_PASS and to_email):
        print("⚠️ Mail config incomplete, skipping onboarding email")
        return

    msg = EmailMessage()
    msg["Subject"] = f"Your LeadsPilotAI Admin Invite for {company_name}"
    msg["From"]    = FROM_EMAIL
    msg["To"]      = to_email

    expiry = (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%d %H:%M UTC")
    body = f"""
Welcome to LeadsPilotAI for {company_name}!

Please click the link below to set your password and access your admin portal:

{invite_link}

This invite expires on {expiry}.
"""
    msg.set_content(body.strip())

    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as smtp:
            smtp.login(SMTP_USER, SMTP_PASS)
            smtp.send_message(msg)
        print(f"✅ Onboarding email sent to {to_email}")
    except Exception as e:
        print(f"❌ Failed to send onboarding email: {e}")


@bp.route('/onboard', methods=['POST'])
def onboard():
    data        = request.get_json() or {}
    name        = data.get('client_name')
    slug        = data.get('client_slug')
    admin_email = data.get('admin_email')
    initial_faqs= data.get('faqs', [])

    if not all([name, slug, admin_email]):
        return jsonify({'error': 'company_name, slug, and admin_email are required'}), 400

    # 1) Create Client
    client_doc = {
        "slug": slug,
        "business_name": name,
        "location": data.get('location', ''),
        "description": data.get('description', ''),
        "calendar_id": data.get('calendar_id', ''),
        "calendar_tokens": data.get('calendar_tokens', {}),
        "faqs": [],  # Will populate later
        "workflows": [],  # Will populate later
        "leads": [],  # Will populate later
        "users": [],  # Will populate later
        "services": [] # will populate later
    }

    client = clients_collection.insert_one(client_doc)
    client_id = client.inserted_id  # MongoDB ObjectId
    
    # 2) Add initial FAQs
    for idx, faq in enumerate(initial_faqs):
        faq_doc = {
            "client_id": client_id,
            "question": faq.get('question', ''),
            "answer": faq.get('answer', ''),
            "sort_order": idx
        }
        faqs_collection.insert_one(faq_doc)

    # 3) Create AdminUser with invite token
    token  = secrets.token_urlsafe(32)
    expiry = datetime.utcnow() + timedelta(days=7)

    admin_user_doc = {
        "email": admin_email,
        "client_id": client_id,
        "invite_token": token,
        "invite_token_expiry": expiry,
        "role": "admin",
        "created_at": datetime.utcnow()
    }
    admin_user = admin_users_collection.insert_one(admin_user_doc)
    admin_user_id = admin_user.inserted_id

    # 4) Add the admin user reference to the client document
    clients_collection.update_one(
        {"_id": ObjectId(client_id)},
        {"$push": {"users": admin_user_id}}
    )

    # 5) Send the invite email
    FRONTEND_URL = os.getenv("FRONTEND_URL", "www.leadspilotai.com")
    invite_link = f"{FRONTEND_URL}/admin/setup?token={token}"
    send_invite_email(name, invite_link, admin_email)

    return jsonify({'success': True, 'client_id': str(client_id)}), 201
