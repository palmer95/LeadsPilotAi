# app.py (The Final, Definitive, Corrected Version)

import os
import json
import requests
from flask import Flask, request, jsonify, make_response
from dotenv import load_dotenv
import logging
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory
from datetime import datetime
from werkzeug.middleware.proxy_fix import ProxyFix
from pymongo import MongoClient
import sales_agent

# Blueprints
from onboard import bp as onboard_bp
from admin_auth import bp as admin_auth_bp
from admin_calendar import bp as calendar_bp
from admin_routes import bp as admin_routes_bp
from api_routes import bp as api_bp

# Setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
load_dotenv()

# --- App & DB Initialization ---
app = Flask(__name__)
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client['leadsPilotAI']

# --- THE FINAL CORS SOLUTION ---
@app.after_request
def after_request(response):
    origin = request.headers.get('Origin')
    
    trusted_origins = [
        "https://www.leadspilotai.com",
        "http://localhost:3000"
    ]

    if origin in trusted_origins:
        response.headers.add('Access-Control-Allow-Origin', origin)
    else:
        # Check the database for the client's domain
        client_doc = db['clients'].find_one({"domain": origin})
        if client_doc:
            response.headers.add('Access-Control-Allow-Origin', origin)
    
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,X-Requested-With')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    response.headers.add('Access-Control-Allow-Credentials', 'true')
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

# --- Register Blueprints ---
app.register_blueprint(onboard_bp)
app.register_blueprint(admin_auth_bp)
app.register_blueprint(calendar_bp)
app.register_blueprint(admin_routes_bp)
app.register_blueprint(api_bp) # Your /api/chat and /api/reset routes

# --- Helper Functions and Shared Resources ---
# These now correctly live in api_routes.py and core.py, this file is just for setup.

# No more route definitions in this file. It's only for configuration and setup.