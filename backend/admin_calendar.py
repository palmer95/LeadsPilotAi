from flask import Blueprint, redirect, request, session, jsonify
import os
import google.auth.transport.requests
from google_auth_oauthlib.flow import Flow
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv

load_dotenv()

# MongoDB setup
mongo_uri = os.getenv('MONGO_URI')
client = MongoClient(mongo_uri)
db = client['leadsPilotAI']

# MongoDB Collections
admin_users_collection = db.admin_users
clients_collection = db.clients

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
    admin_id = session.get("admin_user_id")
    if not admin_id:
        return "Unauthorized", 401

    user = admin_users_collection.find_one({"_id": ObjectId(admin_id)})
    if not user:
        return "User not found", 404

    # Save tokens on user’s client
    client = clients_collection.find_one({"_id": user['client_id']})
    if not client:
        return "Client not found", 404

    calendar_tokens = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes
    }

    clients_collection.update_one(
        {"_id": client['_id']},
        {"$set": {"calendar_tokens": calendar_tokens, "calendar_id": creds.id_token}}
    )

    return redirect("/admin")  # or wherever you want


@bp.route("/status", methods=["GET"])
def calendar_status():
    admin_user_id = session.get("admin_user_id")
    client_slug = session.get("admin_client_slug")

    if not admin_user_id or not client_slug:
        return jsonify({"error": "Unauthorized"}), 401

    client = clients_collection.find_one({"slug": client_slug})
    
    return jsonify({"connected": bool(client and client.get("calendar_tokens"))})


@bp.route("", methods=["GET"])
def calendar_details():
    admin_user_id = session.get("admin_user_id")
    client_slug = session.get("admin_client_slug")

    if not admin_user_id or not client_slug:
        return jsonify({"error": "Unauthorized"}), 401

    client = clients_collection.find_one({"slug": client_slug})

    if not client or not client.get("calendar_tokens"):
        return jsonify({"error": "No calendar connected"}), 404

    return jsonify({
        "calendar_id": client["calendar_id"],
        "tokens": client["calendar_tokens"],
    })
