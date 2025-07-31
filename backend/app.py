# app.py (Final Version - Manual CORS)

import os
from flask import Flask, request, jsonify, make_response
from dotenv import load_dotenv
from pymongo import MongoClient
import logging
from werkzeug.middleware.proxy_fix import ProxyFix
# (Add other necessary imports like langchain, etc. as needed by your blueprints)

# --- Setup ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
load_dotenv()

# --- App & DB Initialization ---
app = Flask(__name__)
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client['leadsPilotAI']

# --- THE FINAL CORS SOLUTION (MANUAL & EXPLICIT) ---
@app.after_request
def after_request(response):
    origin = request.headers.get('Origin')
    
    trusted_origins = [
        "https://www.leadspilotai.com",
        "https://virtourmedia.com",
        "http://localhost:3000"
    ]

    # Dynamically check if the origin is trusted or in the client DB
    if origin in trusted_origins:
        response.headers.set('Access-Control-Allow-Origin', origin)
    else:
        try:
            client_doc = db['clients'].find_one({"domain": origin})
            if client_doc:
                response.headers.set('Access-Control-Allow-Origin', origin)
        except Exception as e:
            logger.error(f"Database lookup for CORS failed: {e}")

    response.headers.set('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.set('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    response.headers.set('Access-Control-Allow-Credentials', 'true')
    return response

@app.route('/api/<path:path>', methods=['OPTIONS'])
def handle_preflight(path):
    # This dedicated route handles the browser's preflight check.
    # The @after_request function above will add the correct headers to this empty response.
    return '', 204
# --- END OF CORS SOLUTION ---


# --- Other App Configurations ---
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.secret_key = os.getenv("FLASK_SECRET_KEY")


# --- Blueprints ---
from onboard import bp as onboard_bp
from admin_auth import bp as admin_auth_bp
from admin_calendar import bp as calendar_bp
from admin_routes import bp as admin_routes_bp
from api_routes import bp as api_bp
from training_routes import bp as training_bp
from analytics_routes import bp as analytics_bp
from service_routes import bp as service_bp

app.register_blueprint(onboard_bp)
app.register_blueprint(admin_auth_bp)
app.register_blueprint(calendar_bp)
app.register_blueprint(admin_routes_bp)
app.register_blueprint(api_bp)
app.register_blueprint(training_bp)
app.register_blueprint(analytics_bp)
app.register_blueprint(service_bp)