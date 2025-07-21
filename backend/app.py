# app.py (The Final, Cleaned Version)
import os
from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
import logging
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from werkzeug.middleware.proxy_fix import ProxyFix
from pymongo import MongoClient
import requests

# --- Setup ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
load_dotenv()

# --- App & DB Initialization ---
app = Flask(__name__)
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client['leadsPilotAI']
conversations_collection = db["conversations"] # Make this accessible for import

# --- Shared Resources for Blueprints ---
llm = ChatOpenAI(temperature=0.3, model="gpt-3.5-turbo", request_timeout=30)
_session_memory: dict[str, any] = {}
_vectorstore_cache: dict[str, FAISS] = {}
_config_cache: dict[str, dict] = {}
CONFIG_BASE_URL = os.getenv("CONFIG_BASE_URL", "https://www.leadspilotai.com")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY is required.")

# --- Helper Functions (accessible for import) ---
def get_config(company: str) -> dict:
    if company not in _config_cache:
        url = f"{CONFIG_BASE_URL}/client-configs/{company}.json"
        try:
            resp = requests.get(url, timeout=5)
            resp.raise_for_status()
            config = resp.json()
            config['slug'] = company
            _config_cache[company] = config
        except requests.RequestException as e:
            raise FileNotFoundError(f"Could not fetch config: {url} -> {e}")
    return _config_cache[company]

def get_vectorstore(company: str) -> FAISS:
    if company not in _vectorstore_cache:
        dirpath = os.path.join(os.path.dirname(__file__), "vectorstores", f"{company}_vectorstore")
        if not os.path.isdir(dirpath):
            raise FileNotFoundError(f"Vectorstore not found: {dirpath}")
        _vectorstore_cache[company] = FAISS.load_local(
            dirpath, OpenAIEmbeddings(), allow_dangerous_deserialization=True
        )
    return _vectorstore_cache[company]

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
from api_routes import bp as api_bp # Import our new blueprint

app.register_blueprint(onboard_bp)
app.register_blueprint(admin_auth_bp)
app.register_blueprint(calendar_bp)
app.register_blueprint(admin_routes_bp)
app.register_blueprint(api_bp) # Register our new blueprint

# NOTE: No more route definitions in this file. It is now just for configuration.