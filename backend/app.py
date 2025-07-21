# app.py
import os
import json
import requests
from flask import Flask, request, jsonify, redirect
#from flask_cors import CORS
from dotenv import load_dotenv
import logging
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory
from datetime import datetime
from werkzeug.middleware.proxy_fix import ProxyFix
from uuid import uuid4
from pymongo import MongoClient

# Import our stateless sales agent and its new state initializer
import sales_agent

# Blueprints (no change)
from onboard import bp as onboard_bp
from admin_auth import bp as admin_auth_bp
from admin_calendar import bp as calendar_bp
from admin_routes import bp as admin_routes_bp

# Set up logging (no change)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Load environment variables (no change)
load_dotenv()
CONFIG_BASE_URL = os.getenv("CONFIG_BASE_URL", "https://www.leadspilotai.com")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY is required.")

app = Flask(__name__)

TRUSTED_ORIGINS = [
    "https://www.leadspilotai.com",
    "http://localhost:3000"
]

@app.after_request
def after_request(response):
    # Get the origin of the incoming request
    origin = request.headers.get('Origin')
    
    # Check if the origin is one of your trusted sites
    if origin in TRUSTED_ORIGINS:
        response.headers.add('Access-Control-Allow-Origin', origin)
    else:
        # If not, check if the origin belongs to an active client in the database
        clients_collection = db['clients']
        client = clients_collection.find_one({"domain": origin})
        if client:
            response.headers.add('Access-Control-Allow-Origin', origin)
            
    # These headers are needed for the browser's preflight requests
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response


# Flask App Configuration (no change)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

# Register Blueprints (no change)
app.register_blueprint(onboard_bp)
app.register_blueprint(admin_auth_bp)
app.register_blueprint(calendar_bp)
app.register_blueprint(admin_routes_bp)



# Database Setup (no change)
MONGO_URI = os.getenv("MONGO_URI")
mongo_client = MongoClient(MONGO_URI)
db = mongo_client['leadsPilotAI']
conversations_collection = db["conversations"]


# Caches for vector stores and configs (no change)
_vectorstore_cache: dict[str, FAISS] = {}
_config_cache: dict[str, dict] = {}

# Per-session memory store for BOTH conversation history and sales agent state
_session_memory: dict[str, any] = {}

# Shared LLM instance (no change)
llm = ChatOpenAI(temperature=0.3, model="gpt-3.5-turbo", request_timeout=30)

# Helper functions for get_config and get_vectorstore (no change)
def get_config(company: str) -> dict:
    if company not in _config_cache:
        url = f"{CONFIG_BASE_URL}/client-configs/{company}.json"
        try:
            resp = requests.get(url, timeout=5)
            resp.raise_for_status()
            config = resp.json()
            # Add slug to config for later use
            config['slug'] = company
            _config_cache[company] = config
        except requests.RequestException as e:
            logger.error(f"Failed to fetch config for {company}: {e}")
            raise FileNotFoundError(f"Could not fetch config: {url} → {e}")
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

### --- CORE LOGIC REFACTORED --- ###

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

    # --- 1. LOAD STATE ---
    # Define unique keys for this user's session
    chat_memory_key = f"chat_history:{company}:{session_id}"
    sales_state_key = f"sales_state:{company}:{session_id}"

    # Load conversation history from memory, or create a new one
    if chat_memory_key not in _session_memory:
        _session_memory[chat_memory_key] = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
    memory = _session_memory[chat_memory_key]

    # Load sales agent state from memory, or create a new one
    current_sales_state = _session_memory.get(sales_state_key, sales_agent.get_initial_state())
    
    # Initialize variables for the response
    response_data = {}
    new_sales_state = current_sales_state

    # --- 2. CALL AGENT / QA CHAIN ---
    user_input = query.lower()
    qa_chain = ConversationalRetrievalChain.from_llm(llm=llm, retriever=vs.as_retriever(search_kwargs={"k": 3}), memory=memory)

    # Determine which logic path to take based on current state
    if sales_agent.is_pricing_inquiry(user_input) and current_sales_state['state'] in ['idle', 'excited']:
        response_data, new_sales_state = sales_agent.handle_pricing_inquiry(CONFIG, current_sales_state)

    elif sales_agent.is_sales_trigger(user_input, CONFIG) and current_sales_state['state'] in ['idle', 'excited']:
        response_data, new_sales_state = sales_agent.start_sales_flow(CONFIG, current_sales_state, user_input)

    elif current_sales_state['state'] in ['engaged', 'booking']:
        response_data, new_sales_state = sales_agent.continue_sales_flow(user_input, CONFIG, current_sales_state)
        
        # Handle the special case where the sales agent needs to perform a QA check
        if response_data.get("response") == "__INFORMATIONAL_QUERY__":
            qa_result = qa_chain.invoke({"question": user_input})
            qa_response_text = qa_result.get("answer", "").strip()
            # Note: You can add your fallback logic for uncertain answers here if needed
            
            # Call the agent AGAIN with the QA response to get the final scripted response
            response_data, new_sales_state = sales_agent.continue_sales_flow(user_input, CONFIG, new_sales_state, qa_response=qa_response_text)
    else:
        # This is a normal QA query
        result = qa_chain.invoke({"question": user_input})
        response_text = result.get("answer", "").strip()
        # Note: You can add your fallback logic for uncertain answers here if needed
        
        # We still need to check if the QA response mentioned a package
        pkg = sales_agent.extract_package(response_text, CONFIG, current_sales_state)
        if pkg:
            new_sales_state = current_sales_state.copy()
            new_sales_state["last_mentioned_package"] = pkg
        
        response_data = {"response": response_text}
        
        # Save conversation turn to DB
        conversations_collection.update_one(
            {"session_id": session_id, "company": company},
            {"$push": {"messages": {"timestamp": datetime.utcnow(), "user": user_input, "bot": response_text}}},
            upsert=True
        )

    # --- 3. SAVE STATE ---
    _session_memory[sales_state_key] = new_sales_state
    
    return jsonify(response_data)


@app.route('/api/reset', methods=['POST'])
def reset():
    data = request.get_json(force=True, silent=True) or {}
    session_id = data.get("session_id", "default")
    company = data.get("company", "unknown")
    
    chat_memory_key = f"chat_history:{company}:{session_id}"
    sales_state_key = f"sales_state:{company}:{session_id}"

    # Delete conversation history memory
    if chat_memory_key in _session_memory:
        del _session_memory[chat_memory_key]
        
    # Delete sales agent state memory
    if sales_state_key in _session_memory:
        del _session_memory[sales_state_key]
        
    logger.info(f"Reset sales flow and chat history for {company}:{session_id}")
    return jsonify({"message": "Sales flow and chat history reset."})


# if __name__ == '__main__':
#     # Note: Using debug=True with multiple workers is not recommended for production.
#     # The in-memory '_session_memory' will not be shared across workers.
#     # This setup is fine for local development and single-worker deployments on Render.
#     app.run(debug=True, host='0.0.0.0', port=int(os.environ.get("PORT", 5050)))