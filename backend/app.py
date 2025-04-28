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
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=False)

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
    """Fetch or return cached client config."""
    if company not in _config_cache:
        url = f"{CONFIG_BASE_URL}/client-configs/{company}.json"
        try:
            resp = requests.get(url, timeout=5)
            resp.raise_for_status()
            _config_cache[company] = resp.json()
        except requests.RequestException as e:
            logger.error(f"Failed to fetch config for {company}: {e}")
            raise FileNotFoundError(f"Could not fetch config: {url} → {e}")
    return _config_cache[company]

def get_vectorstore(company: str) -> FAISS:
    """Load or return cached FAISS index for given company."""
    if company not in _vectorstore_cache:
        dirpath = os.path.join(
            os.path.dirname(__file__),
            "vectorstores",
            f"{company}_vectorstore",
            # Load the latest vector store based on timestamp
            #max(os.listdir(os.path.join(os.path.dirname(__file__), "vectorstores", company)))
        )
        if not os.path.isdir(dirpath):
            logger.error(f"Vectorstore not found: {dirpath}")
            raise FileNotFoundError(f"Vectorstore not found: {dirpath}")
        try:
            _vectorstore_cache[company] = FAISS.load_local(
                dirpath,
                OpenAIEmbeddings(),
                allow_dangerous_deserialization=True  # TODO: Address security risk
            )
        except Exception as e:
            logger.error(f"Failed to load vector store for {company}: {e}")
            raise
    return _vectorstore_cache[company]

# Shared LLM instance
llm = ChatOpenAI(temperature=0.3, model="gpt-3.5-turbo")

# Per-session memory to persist conversation history across requests
_session_memory: dict[str, ConversationBufferMemory] = {}

@app.route('/api/chat', methods=['POST', 'OPTIONS'])
def chat():
    if request.method == 'OPTIONS':
        return '', 204

    data = request.get_json(force=True)
    company = data.get("company")
    query = data.get("query", "").strip()
    session_id = data.get("session_id", "default")  # Add session ID for memory persistence

    if not company or not query:
        return jsonify({"error": "Missing 'company' or 'query' in request body."}), 400

    # Load client config
    try:
        CONFIG = get_config(company)
    except FileNotFoundError as e:
        logger.error(f"Config load failed for {company}: {e}")
        return jsonify({"error": str(e)}), 404

    # Load vector store
    try:
        vs = get_vectorstore(company)
    except FileNotFoundError as e:
        logger.error(f"Vector store load failed for {company}: {e}")
        return jsonify({"error": str(e)}), 404

    # Initialize or retrieve session memory
    memory_key = f"{company}:{session_id}"
    if memory_key not in _session_memory:
        _session_memory[memory_key] = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )
    memory = _session_memory[memory_key]

    # Build QA chain
    qa_chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=vs.as_retriever(search_kwargs={"k": 3}),  # Limit to top 3 results
        memory=memory
    )

    user_input = query.lower()

    # Check for sales flow exit intent
    if sales_agent.is_active() and sales_agent.is_exit_intent(user_input):
        sales_agent.reset_sales_state()
        return jsonify({
            "response": "Got it, let’s step back. How can I help you now?"
        })

    # Handle pricing inquiries
    if not sales_agent.is_active() and sales_agent.is_pricing_inquiry(user_input):
        return jsonify(sales_agent.handle_pricing_inquiry(CONFIG))

    # Handle sales triggers with confirmation
    if not sales_agent.is_active() and sales_agent.is_sales_trigger(user_input, CONFIG):
        try:
            result = sales_agent.start_sales_flow(CONFIG, user_input)
            return jsonify(result)
        except Exception as e:
            logger.exception(f"Error in start_sales_flow for {company}")
            return jsonify({"response": "Sorry, I couldn’t start the booking process. Let’s try something else."}), 500

    # Continue sales flow if active
    if sales_agent.is_active():
        try:
            result = sales_agent.continue_sales_flow(user_input, CONFIG)
            return jsonify(result)
        except Exception as e:
            logger.exception(f"Error in continue_sales_flow for {company}")
            return jsonify({"response": "Sorry, I couldn’t continue the booking process. Let’s try something else."}), 500

    # Normal QA
    try:
        result = qa_chain({"question": user_input})
        response_text = result.get("answer", "").strip()

        # Check if the response mentions a package and update last_mentioned_package
        for pkg in CONFIG["packages"]:
            if pkg["name"].lower() in response_text.lower():
                sales_agent.sales_state["last_mentioned_package"] = pkg["name"]
                break

        # Fallback if LLM is uncertain
        fallback_phrases = [
            "i'm not sure", "i do not have that information",
            "i don't have specific information", "i don't know",
            "i'm sorry", "i don't have information"
        ]
        if (not response_text or
            any(phrase in response_text.lower() for phrase in fallback_phrases)):
            direct = ChatOpenAI(temperature=0.3, model="gpt-3.5-turbo")
            prompt = f"""
You are Clyde 🤓, the AI assistant for {CONFIG['business_name']}.
You help customers by answering questions and capturing lead details.

Business details:
{CONFIG['description']}

User said:
\"\"\"{query}\"\"\"

Respond as Clyde.
"""
            fallback = direct.invoke(prompt)
            response_text = fallback.content.strip()

        return jsonify({"response": response_text})

    except Exception as e:
        logger.error(f"QA error for {company}: {e}")
        return jsonify({"response": "Sorry, I couldn’t process your request. Please try again."}), 500

@app.route('/api/reset', methods=['POST'])
def reset():
    # Clear sales state and session memory
    data = request.get_json(force=True, silent=True) or {}
    session_id = data.get("session_id", "default")
    company = data.get("company", "unknown")
    memory_key = f"{company}:{session_id}"
    sales_agent.reset_sales_state()
    if memory_key in _session_memory:
        del _session_memory[memory_key]
    return jsonify({"message": "Sales flow and chat history reset."})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5050)