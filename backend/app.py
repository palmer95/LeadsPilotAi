# app.py (Final, Corrected, and Complete Version)
import os
import json
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS # <-- Make sure this is not commented out
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

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
CONFIG_BASE_URL = os.getenv("CONFIG_BASE_URL", "https://www.leadspilotai.com")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY is required.")

# --- App & DB Initialization ---
app = Flask(__name__)
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client['leadsPilotAI']

# --- The Definitive CORS Solution ---

# --- The Definitive CORS Solution ---
# These are your own domains that should always be allowed
TRUSTED_ORIGINS = [
    "https://www.leadspilotai.com",
    "http://localhost:3000"
]

@app.after_request
def after_request(response):
    # Get the origin of the incoming request
    origin = request.headers.get('Origin')
    
    # 1. Dynamically check if the origin is trusted or in the client DB
    if origin in TRUSTED_ORIGINS:
        response.headers.add('Access-Control-Allow-Origin', origin)
    else:
        client_doc = db['clients'].find_one({"domain": origin})
        if client_doc:
            response.headers.add('Access-Control-Allow-Origin', origin)
    
    # These headers are needed for both the actual request and preflight
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,X-Requested-With')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response

# 2. Add a dedicated, simple handler for all OPTIONS preflight requests
@app.route('/api/<path:path>', methods=['OPTIONS'])
def handle_options(path):
    # This function's only job is to send back a successful response for the preflight check.
    # The @after_request function above will add the necessary CORS headers.
    return '', 200
# --- Other App Configurations ---
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

# --- Register Blueprints ---
app.register_blueprint(onboard_bp)
app.register_blueprint(admin_auth_bp)
app.register_blueprint(calendar_bp)
app.register_blueprint(admin_routes_bp)

# --- Database & In-Memory Caches ---
conversations_collection = db["conversations"]
_vectorstore_cache: dict[str, FAISS] = {}
_config_cache: dict[str, dict] = {}
_session_memory: dict[str, any] = {}

# --- Shared LLM instance ---
llm = ChatOpenAI(temperature=0.3, model="gpt-3.5-turbo", request_timeout=30)

# --- Helper Functions ---
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
            logger.error(f"Failed to fetch config for {company}: {e}")
            raise FileNotFoundError(f"Could not fetch config: {url} -> {e}")
    return _config_cache[company]

def get_vectorstore(company: str) -> FAISS:
    if company not in _vectorstore_cache:
        dirpath = os.path.join(os.path.dirname(__file__), "vectorstores", f"{company}_vectorstore")
        if not os.path.isdir(dirpath):
            raise FileNotFoundError(f"Vectorstore not found: {dirpath}")
        try:
            _vectorstore_cache[company] = FAISS.load_local(
                dirpath, OpenAIEmbeddings(), allow_dangerous_deserialization=True
            )
        except Exception as e:
            logger.error(f"Failed to load vector store for {company}: {e}")
            raise
    return _vectorstore_cache[company]

# --- Main API Routes ---
@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json(force=True)
    company = data.get("company")
    query = data.get("query", "").strip()
    session_id = data.get("session_id", "default")

    if not company or not query:
        return jsonify({"error": "Missing 'company' or 'query' in request body."}), 400

    try:
        CONFIG = get_config(company)
        vs = get_vectorstore(company)
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404

    chat_memory_key = f"chat_history:{company}:{session_id}"
    sales_state_key = f"sales_state:{company}:{session_id}"

    if chat_memory_key not in _session_memory:
        _session_memory[chat_memory_key] = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
    memory = _session_memory[chat_memory_key]

    current_sales_state = _session_memory.get(sales_state_key, sales_agent.get_initial_state())
    
    response_data = {}
    new_sales_state = current_sales_state
    user_input = query.lower()
    qa_chain = ConversationalRetrievalChain.from_llm(llm=llm, retriever=vs.as_retriever(search_kwargs={"k": 3}), memory=memory)

    if sales_agent.is_pricing_inquiry(user_input) and current_sales_state['state'] in ['idle', 'excited']:
        response_data, new_sales_state = sales_agent.handle_pricing_inquiry(CONFIG, current_sales_state)
    elif sales_agent.is_sales_trigger(user_input, CONFIG) and current_sales_state['state'] in ['idle', 'excited']:
        response_data, new_sales_state = sales_agent.start_sales_flow(CONFIG, current_sales_state, user_input)
    elif current_sales_state['state'] in ['engaged', 'booking']:
        response_data, new_sales_state = sales_agent.continue_sales_flow(user_input, CONFIG, current_sales_state)
        if response_data.get("response") == "__INFORMATIONAL_QUERY__":
            qa_result = qa_chain.invoke({"question": user_input})
            qa_response_text = qa_result.get("answer", "").strip()
            response_data, new_sales_state = sales_agent.continue_sales_flow(user_input, CONFIG, new_sales_state, qa_response=qa_response_text)
    else:
        result = qa_chain.invoke({"question": user_input})
        response_text = result.get("answer", "").strip()
        pkg = sales_agent.extract_package(response_text, CONFIG, current_sales_state)
        if pkg:
            new_sales_state = current_sales_state.copy()
            new_sales_state["last_mentioned_package"] = pkg
        response_data = {"response": response_text}
        conversations_collection.update_one(
            {"session_id": session_id, "company": company},
            {"$push": {"messages": {"timestamp": datetime.utcnow(), "user": user_input, "bot": response_text}}},
            upsert=True
        )

    _session_memory[sales_state_key] = new_sales_state
    
    return jsonify(response_data)

@app.route('/api/reset', methods=['POST'])
def reset():
    data = request.get_json(force=True, silent=True) or {}
    session_id = data.get("session_id", "default")
    company = data.get("company", "unknown")
    
    chat_memory_key = f"chat_history:{company}:{session_id}"
    sales_state_key = f"sales_state:{company}:{session_id}"

    if chat_memory_key in _session_memory:
        del _session_memory[chat_memory_key]
    if sales_state_key in _session_memory:
        del _session_memory[sales_state_key]
        
    logger.info(f"Reset sales flow and chat history for {company}:{session_id}")
    return jsonify({"message": "Sales flow and chat history reset."})