from flask import Blueprint, make_response, redirect, request, jsonify, current_app as app
import os
from google_auth_oauthlib.flow import Flow
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
import logging
import base64
import json
import jwt


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

SCOPES = ["https://www.googleapis.com/auth/calendar",
          "https://www.googleapis.com/auth/userinfo.email",
          "openid",
]



@bp.route("/oauth-start", methods=['GET', 'OPTIONS'])
def oauth_start():
    if request.method == 'OPTIONS':
        logger.info("Handling OPTIONS for oauth-start")
        response = make_response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Authorization'
        return response
    

    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer'):
        logger.error("Missing or invalid authorization header")
        return jsonify({"error": "Missing or invalid token"}), 401
    
    token = auth_header.split(' ')[1]
    try:
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        admin_user_id = payload.get('admin_user_id')
        if not admin_user_id:
            logger.error("No admin_user_id in token payload")
            return jsonify({"error": "Invalid token"}), 401
        logger.info(f"Token payload: {payload}")
    except jwt.ExpiredSignatureError:
        logger.error("Token expired")
        return jsonify({"error": "Token expired"}), 401
    except jwt.InvalidTokenError:
        logger.error("Invalid token")
        return jsonify({"error": "Invalid token"}), 401

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

    state_data = {
        "admin_user_id": admin_user_id,
        "random_state": os.urandom(16).hex()
    }
    state = base64.urlsafe_b64encode(json.dumps(state_data).encode()).decode()

    auth_url, _ = flow.authorization_url(
        access_type="offline",  # so we get a refresh token
        include_granted_scopes="true",
        prompt="consent",
        state=state
    )
    logger.info(f"Current state: {state}")
    logger.info(f"Redirecting to Google OAuth URL: {auth_url}")
    return redirect(auth_url)


@bp.route("/oauth-callback")
def oauth_callback():
    logger.info('In the OAuth callback')
    logger.info(f"Request protocol: {request.scheme}")
    logger.info(f"Request URL: {request.url}")  # Log the full callback URL to inspect query params
    
    state = request.args.get('state')
    code = request.args.get('code')
    
    
    logger.info(f"state in callback: {state}")
    logger.info(f"code in callback: {code}")


    if not state or not code:
        logger.error("Missing state or code in OAuth callback.")
        return "Missing state or code", 400

    try:
        state_data = json.loads(base64.urlsafe_b64decode(state).decode())
        admin_user_id = state_data.get("admin_user_id")
        if not admin_user_id:
            logger.error("No admin_user_id in state")
            return jsonify({"error": "invalid state"}), 400
    except Exception as e:
        logger.error(f"Error decoding state: {e}")
        return "Invalid state", 400

    # The rest of the OAuth logic remains the same
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
        logger.info("Fetching token with the authorization response")
        flow.fetch_token(authorization_response=request.url)
        creds = flow.credentials
        logger.info(f"Successfully retrieved Google Calendar credentials: {creds.token[:10]}...")  # Log token start
    except Exception as e:
        logger.error(f"Error in fetching Google token: {e}")
        return jsonify({"error": "Error in OAuth callback."}), 500

    # Debug: Log credentials to verify successful authentication
    logger.info(f"Google credentials: {creds}")

    # Fetch the user document from MongoDB using the admin_id
    user = admin_users_collection.find_one({"_id": ObjectId(admin_user_id)})
    if not user:
        logger.error(f"User not found for admin ID: {admin_user_id}")
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

# @bp.route("/status", methods=["GET"])
# def calendar_status():
#     admin_user_id = session.get("admin_user_id")
#     client_slug = session.get("admin_client_slug")

#     if not admin_user_id or not client_slug:
#         return jsonify({"error": "Unauthorized"}), 401

#     client = clients_collection.find_one({"slug": client_slug})
    
#     return jsonify({"connected": bool(client and client.get("calendar_tokens"))})


# @bp.route("", methods=["GET"])
# def calendar_details():
#     admin_user_id = session.get("admin_user_id")
#     client_slug = session.get("admin_client_slug")

#     if not admin_user_id or not client_slug:
#         return jsonify({"error": "Unauthorized"}), 401

#     client = clients_collection.find_one({"slug": client_slug})

#     if not client or not client.get("calendar_tokens"):
#         return jsonify({"error": "No calendar connected"}), 404

#     return jsonify({
#         "calendar_id": client["calendar_id"],
#         "tokens": client["calendar_tokens"],
#     })
