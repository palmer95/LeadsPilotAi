# app.py
import os
from flask import Flask
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix
import logging

# 1. Import shared resources from our new core.py file
from core import db

# --- Setup ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# --- App Initialization ---
app = Flask(__name__)

# --- The Definitive CORS Solution ---
def get_allowed_origins(origin, **kwargs):
    trusted_origins = ["https://www.leadspilotai.com", "http://localhost:3000"]
    if origin in trusted_origins:
        return origin
    client_doc = db['clients'].find_one({"domain": origin})
    if client_doc:
        return origin
    return None
CORS(app, origins=get_allowed_origins, supports_credentials=True)

# --- App Configurations ---
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

# --- Import and Register ALL Blueprints ---
from onboard import bp as onboard_bp
from admin_auth import bp as admin_auth_bp
from admin_calendar import bp as calendar_bp
from admin_routes import bp as admin_routes_bp
from api_routes import bp as api_bp

app.register_blueprint(onboard_bp)
app.register_blueprint(admin_auth_bp)
app.register_blueprint(calendar_bp)
app.register_blueprint(admin_routes_bp)
app.register_blueprint(api_bp)