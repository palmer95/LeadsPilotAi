# admin_calendar.py

import os
from flask import Blueprint, redirect, session, url_for, request, jsonify
#from google_auth_oauthlib.flow import Flow

from db import SessionLocal, Client

bp = Blueprint("admin_calendar", __name__, url_prefix="/api/admin/calendar")

# the scopes your app needs
SCOPES = [
    "https://www.googleapis.com/auth/calendar.events.readonly",
    "https://www.googleapis.com/auth/calendar.events"
]

@bp.route("/connect")
def connect():
    flow = Flow.from_client_secrets_file(
        "credentials.json",
        scopes=SCOPES,
        redirect_uri=url_for("admin_calendar.oauth_callback", _external=True)
    )
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes=True
    )
    session["oauth_state"] = state
    return redirect(auth_url)

@bp.route("/callback")
def oauth_callback():
    flow = Flow.from_client_secrets_file(
        "credentials.json",
        scopes=SCOPES,
        state=session.get("oauth_state"),
        redirect_uri=url_for("admin_calendar.oauth_callback", _external=True)
    )
    flow.fetch_token(authorization_response=request.url)
    creds = flow.credentials

    client_slug = session.get("admin_client_slug")
    db = SessionLocal()
    client = db.query(Client).filter_by(slug=client_slug).first()

    client.calendar_tokens = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "expiry": creds.expiry.isoformat(),
        "scopes": creds.scopes
    }
    client.calendar_id = "primary"
    db.commit()

    return jsonify({"success": True, "calendar_id": client.calendar_id})

@bp.route("", methods=["GET"])
def get_settings():
    client_slug = session.get("admin_client_slug")
    db = SessionLocal()
    client = db.query(Client).filter_by(slug=client_slug).first()
    return jsonify({
        "calendar_id": client.calendar_id,
        "connected": bool(client.calendar_tokens)
    })

@bp.route("/disconnect", methods=["POST"])
def disconnect():
    client_slug = session.get("admin_client_slug")
    db = SessionLocal()
    client = db.query(Client).filter_by(slug=client_slug).first()

    client.calendar_tokens = None
    client.calendar_id = None
    db.commit()
    return jsonify({"success": True})
