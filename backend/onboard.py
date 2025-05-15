# backend/onboard.py

import os
import secrets
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage

from flask import Blueprint, request, jsonify, url_for, session
from sqlalchemy.exc import IntegrityError

from db import SessionLocal, Client, AdminUser, FAQ

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

    db = SessionLocal()
    try:
        # 1) create Client
        client = Client(slug=slug, business_name=name)
        db.add(client)
        db.flush()  # get client.id

        # 2) stub FAQs
        for idx, faq in enumerate(initial_faqs):
            db.add(FAQ(
                client_id  = client.id,
                question   = faq.get('question', ''),
                answer     = faq.get('answer', ''),
                sort_order = idx
            ))

        # 3) create AdminUser with invite token
        token  = secrets.token_urlsafe(32)
        expiry = datetime.utcnow() + timedelta(days=7)
        user = AdminUser(
            email               = admin_email,
            client_id           = client.id,
            invite_token        = token,
            invite_token_expiry = expiry
        )
        db.add(user)
        db.commit()

    except IntegrityError:
        db.rollback()
        return jsonify({'error': 'slug or email already in use'}), 409

    # 4) send the invite
    FRONTEND_URL = os.getenv("FRONTEND_URL", "www.leadspilotai.com")
    invite_link = f"{FRONTEND_URL}/admin/login?token={token}"
    send_invite_email(name, invite_link, admin_email)

    return jsonify({'success': True}), 201
