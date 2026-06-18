# api_routes.py (Final Version)

from flask import Blueprint, request, jsonify
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory
from langchain.prompts import PromptTemplate
from datetime import datetime
import sales_agent
import os
import logging
import requests
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.retrievers import MergerRetriever
from langchain.docstore.document import Document

logger = logging.getLogger(__name__)

# Import shared resources from our core.py file
from core import llm, _session_memory, _vectorstore_cache, _config_cache, conversations_collection, db, clients_collection, faqs_collection

# The Blueprint is defined with the /api prefix, so routes are relative to that.
bp = Blueprint('api_routes', __name__, url_prefix='/api')

# --- Helper functions that are specific to this API's logic ---
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
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404

    # The main FAISS vectorstore is optional. Newly onboarded clients may not have
    # one built yet — they can still be answered from their FAQ / training data.
    try:
        vs = get_vectorstore(company)
    except FileNotFoundError:
        logger.warning(f"No FAISS vectorstore for '{company}'; relying on FAQ/training data only.")
        vs = None

    # --- STATE MANAGEMENT (No changes) ---
    chat_memory_key = f"chat_history:{company}:{session_id}"
    sales_state_key = f"sales_state:{company}:{session_id}"
    if chat_memory_key not in _session_memory:
        _session_memory[chat_memory_key] = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
    memory = _session_memory[chat_memory_key]
    current_sales_state = _session_memory.get(sales_state_key, sales_agent.get_initial_state())
    
    # --- KNOWLEDGE RETRIEVAL ---
    # High-priority, client-authored answers come from two collections:
    #   * custom_training — answers added in the admin "training" UI  (keyed by slug)
    #   * faqs            — FAQs captured during onboarding             (keyed by the client's _id)
    # Both are ranked ahead of the main FAISS vectorstore so client answers win,
    # and so a newly onboarded client (no FAISS store yet) can still be answered.
    priority_docs = []
    try:
        for item in db['custom_training'].find({"client_slug": company}):
            if item.get('answer'):
                priority_docs.append(Document(page_content=item['answer'], metadata={'source': item.get('question', '')}))
    except Exception as e:
        logger.warning(f"Could not fetch custom training data for {company}: {e}")

    try:
        client_doc = clients_collection.find_one({"slug": company})
        if client_doc:
            for faq in faqs_collection.find({"client_id": client_doc['_id']}):
                if faq.get('answer'):
                    priority_docs.append(Document(page_content=faq['answer'], metadata={'source': faq.get('question', '')}))
    except Exception as e:
        logger.warning(f"Could not fetch onboarding FAQs for {company}: {e}")

    # Build a layered retriever from whatever knowledge sources exist for this client.
    retrievers = []
    if priority_docs:
        # Cached per-client; rebuilt on restart (see training-cache TODO in CLAUDE.md).
        priority_cache_key = f"{company}_priority_vs"
        if priority_cache_key not in _vectorstore_cache:
            _vectorstore_cache[priority_cache_key] = FAISS.from_documents(priority_docs, OpenAIEmbeddings())
        retrievers.append(_vectorstore_cache[priority_cache_key].as_retriever(search_kwargs={"k": 2}))
    if vs is not None:
        retrievers.append(vs.as_retriever(search_kwargs={"k": 3}))

    if len(retrievers) > 1:
        retriever = MergerRetriever(retrievers=retrievers)
    elif retrievers:
        retriever = retrievers[0]
    else:
        retriever = None

    # Build the QA chain (only possible if the client has any knowledge source).
    business_name = CONFIG.get('business_name', 'this company')
    no_knowledge_reply = (
        "I don't have that specific detail right now — the best next step is to "
        "contact the team directly and they'll be happy to help."
    )
    qa_chain = None
    if retriever is not None:
        qa_prompt = PromptTemplate(
            input_variables=["context", "question"],
            template=(
                f"You are Clyde, an AI sales assistant for {business_name}. "
                "Your job is to help visitors learn about services, pricing, and book appointments. "
                "Answer questions using ONLY the context below. "
                "If the answer is not in the context, say you don't have that specific detail "
                "and suggest the visitor contact the team directly. "
                "Never say you are not affiliated with the company — you are their dedicated assistant.\n\n"
                "Context:\n{context}\n\n"
                "Question: {question}\n"
                "Answer:"
            )
        )
        qa_chain = ConversationalRetrievalChain.from_llm(
            llm=llm,
            retriever=retriever,
            memory=memory,
            combine_docs_chain_kwargs={"prompt": qa_prompt}
        )
    # --- END OF KNOWLEDGE RETRIEVAL ---

    # Initialize variables for the response
    response_data = {}
    new_sales_state = current_sales_state
    user_input = query.lower()

    # --- SALES FLOW LOGIC (No changes) ---
    if sales_agent.is_pricing_inquiry(user_input) and current_sales_state['state'] in ['idle', 'excited']:
        response_data, new_sales_state = sales_agent.handle_pricing_inquiry(CONFIG, current_sales_state)
    elif sales_agent.is_sales_trigger(user_input, CONFIG) and current_sales_state['state'] in ['idle', 'excited']:
        response_data, new_sales_state = sales_agent.start_sales_flow(CONFIG, current_sales_state, user_input)
    elif current_sales_state['state'] in ['engaged', 'booking']:
        response_data, new_sales_state = sales_agent.continue_sales_flow(user_input, CONFIG, current_sales_state)
        if response_data.get("response") == "__INFORMATIONAL_QUERY__":
            if qa_chain is not None:
                qa_result = qa_chain.invoke({"question": user_input})
                qa_response_text = qa_result.get("answer", "").strip() or no_knowledge_reply
            else:
                qa_response_text = no_knowledge_reply
            response_data, new_sales_state = sales_agent.continue_sales_flow(user_input, CONFIG, new_sales_state, qa_response=qa_response_text)
    else:
        # This is the normal QA query
        if qa_chain is not None:
            result = qa_chain.invoke({"question": user_input})
            response_text = result.get("answer", "").strip() or no_knowledge_reply
        else:
            response_text = no_knowledge_reply

        pkg = sales_agent.extract_package(response_text, CONFIG, current_sales_state)
        if pkg:
            new_sales_state = current_sales_state.copy()
            new_sales_state["last_mentioned_package"] = pkg
        
        response_data = {"response": response_text}
    
    # --- SAVE CONVERSATION TO MONGODB ---
    response_text_to_save = response_data.get("response", "No response generated.")
    try:
        conversations_collection.update_one(
            {"session_id": session_id, "company": company},
            {"$push": {"messages": {"timestamp": datetime.utcnow(), "user": query, "bot": response_text_to_save}}},
            upsert=True
        )
    except Exception as e:
        logger.warning(f"Could not save conversation to MongoDB: {e}")



    # --- SAVE SESSION STATE (No changes) ---
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
