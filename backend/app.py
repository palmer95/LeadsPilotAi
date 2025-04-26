# app.py
import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory

import sales_agent

load_dotenv()

app = Flask(__name__)
# Allow widget calls from any origin (your clients’ domains)
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

# Caches to avoid re-loading indexes/configs on every call
_vectorstore_cache: dict[str, FAISS] = {}
_config_cache: dict[str, dict] = {}

def get_config(company: str) -> dict:
    """Load or return cached client config JSON."""
    if company not in _config_cache:
        path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "client-configs",
            f"{company}.json"
        )
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Config file not found: {path}")
        with open(path) as f:
            _config_cache[company] = json.load(f)
    return _config_cache[company]

def get_vectorstore(company: str) -> FAISS:
    """Load or return cached FAISS index for given company."""
    if company not in _vectorstore_cache:
        dirpath = os.path.join(
            os.path.dirname(__file__),
            "..",
            f"{company}_vectorstore"
        )
        if not os.path.isdir(dirpath):
            raise FileNotFoundError(f"Vectorstore not found: {dirpath}")
        _vectorstore_cache[company] = FAISS.load_local(
            dirpath,
            OpenAIEmbeddings(),
            allow_dangerous_deserialization=True
        )
    return _vectorstore_cache[company]

# Shared LLM instance
llm = ChatOpenAI(temperature=0.3, model="gpt-3.5-turbo")

@app.route('/api/chat', methods=['POST', 'OPTIONS'])
def chat():
    if request.method == 'OPTIONS':
        # flask-cors handles this automatically
        return '', 204

    data = request.get_json(force=True)
    company = data.get("company")
    query   = data.get("query", "").strip()

    if not company or not query:
        return jsonify({"error": "Missing 'company' or 'query' in request body."}), 400

    # 1) Load client config
    try:
        CONFIG = get_config(company)
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404

    # 2) Load vectorstore + build chain with fresh memory
    try:
        vs = get_vectorstore(company)
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404

    memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
    qa_chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=vs.as_retriever(),
        memory=memory
    )

    user_input = query.lower()

    # 3) Sales-agent shortcuts
    if not sales_agent.is_active() and sales_agent.is_pricing_inquiry(user_input):
        return jsonify(sales_agent.handle_pricing_inquiry(CONFIG))

    if not sales_agent.is_active() and sales_agent.is_sales_trigger(user_input, CONFIG):
        return jsonify(sales_agent.start_sales_flow(CONFIG))

    if sales_agent.is_active():
        return jsonify(sales_agent.continue_sales_flow(user_input, CONFIG))

    # 4) Normal QA
    try:
        result = qa_chain({"question": user_input})
        response_text = result.get("answer", "").strip()

        # Fallback if LLM is uncertain
        fallback_phrases = [
            "i'm not sure", "i do not have that information",
            "i don't have specific information", "i don't know",
            "i'm sorry"
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
        app.logger.error("QA error for %s: %s", company, e)
        return jsonify({"response": "Something went wrong processing your request."}), 500

@app.route('/api/reset', methods=['POST'])
def reset():
    # Clear only sales-agent state; memory is per-request now
    sales_agent.reset_sales_state()
    return jsonify({"message": "Sales flow and chat history reset."})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5050)
