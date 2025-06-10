# app.py
import os
import json
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import logging
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory
from datetime import datetime

from onboard import bp as onboard_bp
from admin_auth import bp as admin_auth_bp
from admin_calendar import bp as calendar_bp
from admin_routes import bp as admin_routes_bp



import sales_agent


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

# Load environment variables
load_dotenv()
CONFIG_BASE_URL = os.getenv("CONFIG_BASE_URL", "https://www.leadspilotai.com")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.error("OPENAI_API_KEY not found in environment variables.")
    raise ValueError("OPENAI_API_KEY is required.")

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "super-secret-key")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SECURE"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"  # Required for cross-site cookies
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour session expiry
app.config["SESSION_COOKIE_NAME"] = "leadspilot_session"
# Enable CORS
CORS(app, supports_credentials=True)  # This allows credentials but will be controlled dynamically

@app.before_request
def log_request():
    logger.info(f"Incoming request: {request.method} {request.url}")

@app.after_request
def apply_cors_headers(response):
    origin = request.headers.get("Origin")
    allowed_origins = ["https://www.leadspilotai.com", "https://leadspilotai.onrender.com"]

    # Ensure that the Origin header is correctly set
    if origin in allowed_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With, Accept"
        response.headers["Vary"] = "Origin"  # Important to vary the origin for credentials

    return response

# 🚀 Explicit Preflight Handler for OPTIONS (SOLVES PRE-FLIGHT ISSUES)
@app.route('/api/<path:path>', methods=['OPTIONS'])
def handle_preflight(path):
    response = jsonify({"message": "Preflight handled."})
    response.status_code = 204
    origin = request.headers.get("Origin")
    allowed_origins = ["https://www.leadspilotai.com", "https://leadspilotai.onrender.com"]

    if origin in allowed_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With, Accept"

    return response

# API /api endpoints
app.register_blueprint(onboard_bp)
app.register_blueprint(admin_auth_bp)
app.register_blueprint(calendar_bp)
app.register_blueprint(admin_routes_bp)



# Caches for vector stores and configs
_vectorstore_cache: dict[str, FAISS] = {}
_config_cache: dict[str, dict] = {}

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response

def get_config(company: str) -> dict:
    if company not in _config_cache:
        url = f"{CONFIG_BASE_URL}/client-configs/{company}.json"
        try:
            resp = requests.get(url, timeout=5)
            resp.raise_for_status()
            config = resp.json()
            required_fields = ["business_name", "packages", "qualifying_questions"]
            for field in required_fields:
                if field not in config:
                    raise ValueError(f"Missing required config field: {field}")
            for pkg in config.get("packages", []):
                pkg_name = pkg.get("name", "")
                if not pkg_name or not all(c.isalnum() or c in " -_" for c in pkg_name):
                    raise ValueError(f"Invalid package name: {pkg_name}")
            _config_cache[company] = config
        except requests.RequestException as e:
            logger.error(f"Failed to fetch config for {company}: {e}")
            raise FileNotFoundError(f"Could not fetch config: {url} → {e}")
        except ValueError as e:
            logger.error(f"Invalid config for {company}: {e}")
            raise
    return _config_cache[company]

def get_vectorstore(company: str) -> FAISS:
    if company not in _vectorstore_cache:
        dirpath = os.path.join(
            os.path.dirname(__file__),
            "vectorstores",
            f"{company}_vectorstore"
        )
        if not os.path.isdir(dirpath):
            logger.error(f"Vectorstore not found: {dirpath}")
            raise FileNotFoundError(f"Vectorstore not found: {dirpath}")
        try:
            _vectorstore_cache[company] = FAISS.load_local(
                dirpath,
                OpenAIEmbeddings(),
                allow_dangerous_deserialization=True
            )
        except Exception as e:
            logger.error(f"Failed to load vector store for {company}: {e}")
            raise
    return _vectorstore_cache[company]

# Shared LLM instance with timeout
llm = ChatOpenAI(temperature=0.3, model="gpt-3.5-turbo", request_timeout=30)

# Per-session memory to persist conversation history across requests
_session_memory: dict[str, ConversationBufferMemory] = {}

@app.route('/api/chat', methods=['POST', 'OPTIONS'])
def chat():
    if request.method == 'OPTIONS':
        return '', 204

    data = request.get_json(force=True)
    company = data.get("company")
    query = data.get("query", "").strip()
    session_id = data.get("session_id", "default")

    if not company or not query:
        return jsonify({"error": "Missing 'company' or 'query' in request body."}), 400

    try:
        CONFIG = get_config(company)
    except FileNotFoundError as e:
        logger.error(f"Config load failed for {company}: {e}")
        return jsonify({"error": str(e)}), 404
    except ValueError as e:
        logger.error(f"Config validation failed for {company}: {e}")
        return jsonify({"error": str(e)}), 400

    try:
        vs = get_vectorstore(company)
    except FileNotFoundError as e:
        logger.error(f"Vector store load failed for {company}: {e}")
        return jsonify({"error": str(e)}), 404

    memory_key = f"{company}:{session_id}"
    if memory_key not in _session_memory:
        _session_memory[memory_key] = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )
    memory = _session_memory[memory_key]

    qa_chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=vs.as_retriever(search_kwargs={"k": 3}),
        memory=memory
    )

    user_input = query.lower()

    # Handle pricing inquiries (transition to engaged state)
    if sales_agent.sales_state["state"] in ["idle", "excited"] and sales_agent.is_pricing_inquiry(user_input):
        logger.info(f"Pricing inquiry detected for {company}: {user_input}")
        return jsonify(sales_agent.handle_pricing_inquiry(CONFIG))
    
    # 2) Suggested‐FAQ clicks → always QA, never sales
    if sales_agent.sales_state["state"] in ["idle", "excited"] and user_input in CONFIG.get("faqs", []):
        answer = qa_chain({"question": user_input}).get("answer", "")
        return jsonify({"response": answer})

    # Handle sales triggers (transition to booking state)
    if sales_agent.sales_state["state"] in ["idle", "excited"]:
        if sales_agent.is_sales_trigger(user_input, CONFIG):
                result = sales_agent.start_sales_flow(CONFIG, user_input)
                return jsonify(result)

    # Continue sales flow if in engaged or booking state
    if sales_agent.sales_state["state"] in ["engaged", "booking"]:
        try:
            selected_package = sales_agent.extract_package(user_input, CONFIG)
            logger.info(f"Package extraction in sales flow for {company}: {user_input} → {selected_package}")
            result = sales_agent.continue_sales_flow(user_input, CONFIG)
            logger.info(f"Continuing sales flow for {company}: {user_input}")

            # Handle informational queries
            if result["response"] == "__INFORMATIONAL_QUERY__":
                logger.info(f"Informational query detected for {company}: {user_input}")
                qa_result = qa_chain({"question": user_input})
                response_text = qa_result.get("answer", "").strip()
                logger.info(f"QA response for informational query: {response_text[:100]}...")

                for pkg in CONFIG["packages"]:
                    if pkg["name"].lower() in response_text.lower():
                        sales_agent.sales_state["last_mentioned_package"] = pkg["name"]
                        logger.info(f"Updated last_mentioned_package to {pkg['name']} based on QA response")
                        break

                fallback_phrases = [
                    "i'm not sure", "i do not have that information",
                    "i don't have specific information", "i don't know",
                    "i'm sorry", "i don't have information"
                ]

                if (not response_text or
                    any(phrase in response_text.lower() for phrase in fallback_phrases)):
                    logger.info(f"QA response uncertain, triggering fallback for {company}")
                    direct = ChatOpenAI(temperature=0.3, model="gpt-3.5-turbo", request_timeout=30)
                    prompt = f"""
You are Clyde 🤓, the AI assistant for {CONFIG['business_name']}.
You help customers by answering questions and capturing lead details.

Business details:
{CONFIG['description']}

User said:
\"\"\"{query}\"\"

Respond as Clyde.
"""
                    fallback = direct.invoke(prompt)
                    response_text = fallback.content.strip()
                    logger.info(f"Fallback response for {company}: {response_text[:100]}...")

                    for pkg in CONFIG["packages"]:
                        if pkg["name"].lower() in response_text.lower():
                            sales_agent.sales_state["last_mentioned_package"] = pkg["name"]
                            logger.info(f"Updated last_mentioned_package to {pkg['name']} based on fallback response")
                            break

                # Pass the QA response back to continue_sales_flow to append the follow-up prompt
                result = sales_agent.continue_sales_flow(user_input, CONFIG, qa_response=response_text)
                return jsonify(result)

            return jsonify(result)
        except Exception as e:
            logger.exception(f"Error in continue_sales_flow for {company}")
            return jsonify({"response": "Sorry, I couldn’t continue the booking process. Let’s try something else."}), 500

    # Normal QA for idle or excited state
    try:
        logger.info(f"Processing QA for {company}: {user_input}")
        result = qa_chain({"question": user_input})
        response_text = result.get("answer", "").strip()
        logger.info(f"QA response for {company}: {response_text[:100]}...")

        for pkg in CONFIG["packages"]:
            if pkg["name"].lower() in response_text.lower():
                sales_agent.sales_state["last_mentioned_package"] = pkg["name"]
                logger.info(f"Updated last_mentioned_package to {pkg['name']} based on QA response")
                break

        fallback_phrases = [
            "i'm not sure", "i do not have that information",
            "i don't have specific information", "i don't know"
        ]
        if (not response_text or
            any(phrase in response_text.lower() for phrase in fallback_phrases)):
            logger.info(f"QA response uncertain, triggering fallback for {company}")
            direct = ChatOpenAI(temperature=0.3, model="gpt-3.5-turbo", request_timeout=30)
            prompt = f"""
You are Clyde 🤓, the AI assistant for {CONFIG['business_name']}.
You help customers by answering questions and capturing lead details.

Business details:
{CONFIG['description']}

User said:
\"\"\"{query}\"\"

Respond as Clyde.
"""
            fallback = direct.invoke(prompt)
            response_text = fallback.content.strip()
            logger.info(f"Fallback response for {company}: {response_text[:100]}...")

            for pkg in CONFIG["packages"]:
                if pkg["name"].lower() in response_text.lower():
                    sales_agent.sales_state["last_mentioned_package"] = pkg["name"]
                    logger.info(f"Updated last_mentioned_package to {pkg['name']} based on fallback response")
                    break

        return jsonify({"response": response_text})

    except Exception as e:
        logger.error(f"QA error for {company}: {e}")
        return jsonify({"response": "Sorry, I couldn’t process your request. Please try again."}), 500

@app.route('/api/reset', methods=['POST'])
def reset():
    data = request.get_json(force=True, silent=True) or {}
    session_id = data.get("session_id", "default")
    company = data.get("company", "unknown")
    memory_key = f"{company}:{session_id}"
    sales_agent.reset_sales_state()
    if memory_key in _session_memory:
        del _session_memory[memory_key]
    logger.info(f"Reset sales flow and chat history for {company}")
    return jsonify({"message": "Sales flow and chat history reset."})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5050)