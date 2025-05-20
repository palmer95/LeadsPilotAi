# backend/admin_routes.py
from flask import Blueprint, request, jsonify, session
from db import SessionLocal, Lead, FAQ, AdminUser
from flask_cors import CORS


bp = Blueprint('admin_routes', __name__, url_prefix='/api/admin/data')
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