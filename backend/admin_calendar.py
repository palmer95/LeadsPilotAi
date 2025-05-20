# admin_calendar.py

from flask import Blueprint, redirect, request, session, jsonify
import os
import google.auth.transport.requests
from google_auth_oauthlib.flow import Flow
from db import SessionLocal, AdminUser

bp = Blueprint('calendar', __name__, url_prefix='/api/admin/calendar')

SCOPES = ["https://www.googleapis.com/auth/calendar"]

@bp.route("/oauth-start")
def oauth_start():
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": os.environ["GOOGLE_CLIENT_ID"],
                "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
                "redirect_uris": [os.environ["GOOGLE_REDIRECT_URI"]],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES,
        redirect_uri=os.environ["GOOGLE_REDIRECT_URI"]
    )

    auth_url, state = flow.authorization_url(
        access_type="offline",  # so we get a refresh token
        include_granted_scopes="true",
        prompt="consent"
    )
    session["oauth_state"] = state
    return redirect(auth_url)


@bp.route("/oauth-callback")
def oauth_callback():
    state = session.get("oauth_state")
    if not state:
        return "Missing state", 400

    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": os.environ["GOOGLE_CLIENT_ID"],
                "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
                "redirect_uris": [os.environ["GOOGLE_REDIRECT_URI"]],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES,
        redirect_uri=os.environ["GOOGLE_REDIRECT_URI"]
    )

    flow.fetch_token(authorization_response=request.url)

    creds = flow.credentials
    db = SessionLocal()

    admin_id = session.get("admin_user_id")
    if not admin_id:
        return "Unauthorized", 401

    user = db.query(AdminUser).filter_by(id=admin_id).first()
    if not user:
        return "User not found", 404

    # Save tokens on user’s client
    client = user.client
    client.calendar_tokens = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes
    }
    db.commit()
    return redirect("/admin")  # or wherever you want
