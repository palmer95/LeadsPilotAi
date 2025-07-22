from flask import Blueprint, request, jsonify
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory
from datetime import datetime
import sales_agent
import os
import requests 
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

# 1. Import all shared resources from our core.py file
from core import llm, _session_memory, _vectorstore_cache, _config_cache, db, conversations_collection

bp = Blueprint('api_routes', __name__, url_prefix='/api')

# --- Helper functions ---
CONFIG_BASE_URL = os.getenv("CONFIG_BASE_URL", "https://www.leadspilotai.com")

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

# The route decorator should just be '/chat', not '/api/chat', 
# because the '/api' prefix is already defined in the Blueprint.
@bp.route('/chat', methods=['POST'])
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
        
        # This will now work because conversations_collection is imported
        conversations_collection.update_one(
            {"session_id": session_id, "company": company},
            {"$push": {"messages": {"timestamp": datetime.utcnow(), "user": user_input, "bot": response_text}}},
            upsert=True
        )

    _session_memory[sales_state_key] = new_sales_state
    
    return jsonify(response_data)


@bp.route('/reset', methods=['POST'])
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
        
    return jsonify({"message": "Session reset."})