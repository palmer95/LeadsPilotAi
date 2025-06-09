from flask import Blueprint, redirect, request, session, jsonify
import os
import google.auth.transport.requests
from google_auth_oauthlib.flow import Flow
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
import logging

load_dotenv()

# setup logging
# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


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
    logger.info("Starting OAuth process...")

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
    logger.info(f"Redirecting to Google OAuth URL: {auth_url}")
    return redirect(auth_url)


@bp.route("/oauth-callback")
def oauth_callback():
    logger.info('In the OAuth callback')

    state = session.get("oauth_state")
    if not state:
        logger.error("Missing state in OAuth callback.")
        return "Missing state", 400

    # Create the OAuth flow from the client configuration
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

    # Fetch the token using the response from Google
    try:
        flow.fetch_token(authorization_response=request.url)
        creds = flow.credentials
        logger.info(f"Successfully retrieved Google Calendar credentials: {creds.token[:10]}...")  # Log token start
    except Exception as e:
        logger.error(f"Error in fetching Google token: {e}")
        return jsonify({"error": "Error in OAuth callback."}), 500

    # Debug: Log credentials to verify successful authentication
    logger.info(f"Google credentials: {creds}")

    admin_id = session.get("admin_user_id")
    if not admin_id:
        logger.error("Admin ID not found in session.")
        return "Unauthorized", 401

    # Fetch the user document from MongoDB using the admin_id
    user = admin_users_collection.find_one({"_id": ObjectId(admin_id)})
    if not user:
        logger.error(f"User not found for admin ID: {admin_id}")
        return "User not found", 404

    # Fetch the client document associated with the user
    client = clients_collection.find_one({"_id": user['client_id']})
    if not client:
        logger.error(f"Client not found for user: {user['email']}")
        return "Client not found", 404

    # Prepare the calendar tokens to be saved
    calendar_tokens = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes
    }

    # Update the client document in MongoDB with the calendar tokens
    result = clients_collection.update_one(
        {"_id": client['_id']},
        {"$set": {"calendar_tokens": calendar_tokens, "calendar_id": creds.id_token}}
    )

    if result.matched_count == 0:
        logger.error(f"Failed to update client with calendar tokens. Client ID: {client['_id']}")
        return "Failed to save calendar tokens", 500

    # Debug: Log success and return redirect
    logger.info(f"Successfully updated calendar tokens for client: {client['_id']}")
    return redirect("/admin")  # Redirect to admin page after success

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
