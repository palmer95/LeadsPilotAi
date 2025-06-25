from zoneinfo import ZoneInfo
from flask import Blueprint, make_response, redirect, request, jsonify, current_app as app
import os
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from datetime import datetime, timedelta, timezone
from dateutil import parser
from pytz import timezone as pytz_timezone
from config_utils import get_config
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
import logging
import base64
import json
import jwt
import googleapiclient.discovery


load_dotenv()

local_tz = pytz_timezone("America/Los_Angeles")  # For Pacific Time, later pull this from client config


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
        response = make_response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Authorization'
        return response

    logger.info(f"Request headers: {dict(request.headers)}")
    token = request.args.get('token')
    if not token:
        logger.error("Missing token in query parameter")
        return create_response({"error": "Missing token"}, 401)

    try:
        payload = jwt.decode(token, os.getenv('FLASK_SECRET_KEY'), algorithms=['HS256'], options={"verify_exp": False})  # Temporary for testing
        admin_user_id = payload.get('admin_user_id')
        if not admin_user_id:
            logger.error("No admin_user_id in token payload")
            return create_response({"error": "Invalid token"}, 401)
        logger.info(f"Token payload: {payload}")
    except jwt.ExpiredSignatureError:
        logger.error("Token expired")
        return create_response({"error": "Token expired"}, 401)
    except jwt.InvalidTokenError as e:
        logger.error(f"Invalid token: {str(e)}")
        return create_response({"error": "Invalid token"}, 401)

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
        access_type="offline",
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
    # result = clients_collection.update_one(
    #     {"_id": client['_id']},
    #     {"$set": {"calendar_tokens": calendar_tokens, "calendar_id": creds.id_token}}
    # )

    service = build("calendar", "v3", credentials=creds)
    calendar_list = service.calendarList().list().execute()
    primary_calendar = next((c for c in calendar_list["items"] if c.get("primary")), None)
    calendar_id = primary_calendar["id"] if primary_calendar else None


    logger.info(f"creds.id_token: {getattr(creds, 'id_token', None)}")
    result = clients_collection.update_one(
        {"_id": client['_id']},
        {"$set": {"calendar_tokens": calendar_tokens, "calendar_id": calendar_id}}
    )

    if result.matched_count == 0:
        logger.error(f"Failed to update client with calendar tokens. Client ID: {client['_id']}")
        return "Failed to save calendar tokens", 500

    # Debug: Log success and return redirect
    logger.info(f"Successfully updated calendar tokens for client: {client['_id']}")
    return redirect("https://www.leadspilotai.com/admin")


def create_response(data, status=200):
    response = make_response(jsonify(data), status)
    response.headers['Access-Control-Allow-Origin'] = 'https://www.leadspilotai.com'
    response.headers['Access-Control-Allow-Headers'] = 'Authorization, Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'    
    return response

def get_business_hours(config):
    default_hours = {
        "monday": ["09:00", "17:00"],
        "tuesday": ["09:00", "17:00"],
        "wednesday": ["09:00", "17:00"],
        "thursday": ["09:00", "17:00"],
        "friday": ["09:00", "17:00"]
    }
    return config.get("business_hours", default_hours)

@bp.route("/slots", methods=["GET"])
def get_slots():
    company = request.args.get("company")
    if not company:
        return jsonify({"error": "Missing 'company' param"}), 400

    try:
        config = get_config(company)
    except Exception as e:
        logger.error(f"Failed to load config for {company}: {e}")
        return jsonify({"error": "Failed to load business config"}), 500

    # Use config-defined hours or fallback
    business_hours = get_business_hours(config)
    tz_local = pytz_timezone("America/Los_Angeles")
    now = datetime.now(tz_local)
    today = now.date()

    days_ahead = 7
    available_slots = []

    for i in range(days_ahead):
        day = today + timedelta(days=i)
        weekday_name = day.strftime("%A").lower()

        if weekday_name not in business_hours:
            continue  # skip weekends or undefined days

        open_str, close_str = business_hours[weekday_name]
        open_time = datetime.strptime(open_str, "%H:%M").time()
        close_time = datetime.strptime(close_str, "%H:%M").time()

        current = tz_local.localize(datetime.combine(day, open_time))
        end = tz_local.localize(datetime.combine(day, close_time))

        while current < end:
            if current > now:
                available_slots.append(current.isoformat())
            current += timedelta(minutes=30)

    return jsonify({"slots": available_slots})

@bp.route("/slotsOLD", methods=["GET", "OPTIONS"])
def get_slotsOLD():
    if request.method == 'OPTIONS':
        response = make_response()
        response.status_code = 200
        response.headers['Access-Control-Allow-Origin'] = 'https://www.leadspilotai.com'
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Authorization, Content-Type'
        return response

   # this assumes its the actual client_slug
    company = request.args.get('company')
    if not company:
        return create_response({"error": "Missing company"}, 403)

    client = clients_collection.find_one({"slug": company})
    if not client or not client.get("calendar_tokens"):
        return create_response({"error": "Calendar not connected"}, 404)

    creds = Credentials(
        token=client["calendar_tokens"]["token"],
        refresh_token=client["calendar_tokens"]["refresh_token"],
        token_uri=client["calendar_tokens"]["token_uri"],
        client_id=client["calendar_tokens"]["client_id"],
        client_secret=client["calendar_tokens"]["client_secret"],
        scopes=client["calendar_tokens"]["scopes"]
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        clients_collection.update_one(
            {"_id": client['_id']},
            {"$set": {"calendar_tokens": {
                "token": creds.token,
                "refresh_token": creds.refresh_token,
                "token_uri": creds.token_uri,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "scopes": creds.scopes
            }}}
        )

    service = build('calendar', 'v3', credentials=creds)
    now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    end = now + timedelta(days=7)
    
    freebusy = service.freebusy().query(body={
        "timeMin": now.isoformat() + 'Z',
        "timeMax": end.isoformat() + 'Z',
        "items": [{"id": "primary"}]
    }).execute()

    busy = freebusy["calendars"]["primary"]["busy"]
    slots = []
    current = now
    while current < end:
        slot_end = current + timedelta(minutes=30)
        if not any(
            datetime.fromisoformat(b["start"].rstrip("Z")) < slot_end and
            datetime.fromisoformat(b["end"].rstrip("Z")) > current
            for b in busy
        ):
            slots.append(current.isoformat())
        current = slot_end
    return create_response({"slots": slots[:20]})

@bp.route("/calendar/week", methods=["GET", "OPTIONS"])
def get_week_calendar():
    if request.method == "OPTIONS":
        response = make_response()
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
        return response
    return jsonify({"status": "Endpoint working"}), 200

@bp.route("/book", methods=["POST", "OPTIONS"])
def book_appointment():
    if request.method == 'OPTIONS':
        response = make_response()
        response.status_code = 200
        response.headers['Access-Control-Allow-Origin'] = 'https://www.leadspilotai.com'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Authorization, Content-Type'
        return response

   

    data = request.get_json() or {}
    slot = data.get("slot")
    name = data.get("name")
    email = data.get("email")
    notes = data.get("notes", "")
    company = data.get("company")

    if not slot or not name or not email or not company:
        return create_response({"error": "Missing or invalid fields"}, 400)
    
    client_slug = company


    client = clients_collection.find_one({"slug": client_slug})
    if not client or not client.get("calendar_tokens"):
        return create_response({"error": "Calendar not connected"}, 404)

    creds = Credentials(
        token=client["calendar_tokens"]["token"],
        refresh_token=client["calendar_tokens"]["refresh_token"],
        token_uri=client["calendar_tokens"]["token_uri"],
        client_id=client["calendar_tokens"]["client_id"],
        client_secret=client["calendar_tokens"]["client_secret"],
        scopes=client["calendar_tokens"]["scopes"]
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        clients_collection.update_one(
            {"_id": client['_id']},
            {"$set": {"calendar_tokens": {
                "token": creds.token,
                "refresh_token": creds.refresh_token,
                "token_uri": creds.token_uri,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "scopes": creds.scopes
            }}}
        )

    logger.info(f"Raw slot from frontend: {slot}")

    service = build('calendar', 'v3', credentials=creds)

    # DO NOT TOUCH THIS BLOCK GETTING THIS WORKING WAS A NIGHTMARE IT WORKS NOW LEAVE IT ALONE
    try:
        # Slot from frontend is UTC — make it aware
        start = parser.isoparse(slot).replace(tzinfo=ZoneInfo("America/Los_Angeles"))
        start = start.replace(minute=(start.minute // 30) * 30, second=0, microsecond=0)
        end = start + timedelta(minutes=30)

        # freebusy requires RFC3339 timestamp with 'Z'
        time_min = start.isoformat().replace('+00:00', 'Z')
        time_max = end.isoformat().replace('+00:00', 'Z')

        logger.info(f"timeMin: {time_min}, timeMax: {time_max}")

        # Confirm slot still free
        freebusy = service.freebusy().query(body={
            "timeMin": time_min,
            "timeMax": time_max,
            "items": [{"id": "primary"}]
        }).execute()

        if freebusy["calendars"]["primary"]["busy"]:
            return create_response({"error": "Slot is no longer available"}, 409)

        pacific = ZoneInfo("America/Los_Angeles")
        start_local = start.astimezone(pacific)
        end_local = start.astimezone(pacific)
        # Book the event
        event = {
            'summary': f'Phone call with {name}',
            'description': f'Email: {email}\nNotes: {notes}',
            'start': {
                'dateTime': start_local.isoformat(),
                'timeZone': 'America/Los_Angeles'
            },
            'end': {
                'dateTime': end_local.isoformat(),
                'timeZone': 'America/Los_Angeles'
            },
            'attendees': [{'email': email}],
        }

        # Double-check slot is still free before booking
        freebusy_check = service.freebusy().query(body={
            "timeMin": time_min,
            "timeMax": time_max,
            "items": [{"id": "primary"}]
        }).execute()

        if freebusy_check["calendars"]["primary"]["busy"]:
            return create_response({"error": "Slot just got taken"}, 409)

        service.events().insert(
            calendarId='primary',
            body=event,
            sendUpdates='all'
        ).execute()
        return create_response({"success": True})
    except Exception as e:
        logger.error(f"Error creating event: {e}")
        return create_response({"error": "Failed to book appointment"}, 500)

@bp.route("", methods=["GET", "OPTIONS"])
@bp.route("/", methods=["GET", "OPTIONS"])
def calendar_details():
    if request.method == 'OPTIONS':
        logger.info("Handling OPTIONS for calendar_details")
        response = make_response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Authorization'
        return response

    logger.info(f"Request headers: {dict(request.headers)}")
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        logger.error("Missing or invalid Authorization header")
        return create_response({"error": "Missing or invalid token"}, 401)

    token = auth_header.split(' ')[1]
    try:
        payload = jwt.decode(token, os.getenv('FLASK_SECRET_KEY'), algorithms=['HS256'])
        client_slug = payload.get('admin_client_slug')
        if not client_slug:
            logger.error("Invalid token payload")
            return create_response({"error": "Invalid token"}, 401)
        logger.info(f"Token payload: {payload}")
    except jwt.ExpiredSignatureError:
        logger.error("Token expired")
        return create_response({"error": "Token expired"}, 401)
    except jwt.InvalidTokenError:
        logger.error("Invalid token")
        return create_response({"error": "Invalid token"}, 401)

    client = clients_collection.find_one({"slug": client_slug})
    if not client:
        logger.error(f"Client not found for slug: {client_slug}")
        return create_response({"error": "Client not found"}, 404)

    connected = bool(client.get("calendar_tokens"))
    return create_response({"connected": connected})