import os
import certifi
from pymongo import MongoClient
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

# Initialize core services to be shared
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=3000)
db = client['leadsPilotAI']

#collections
conversations_collection = db['conversations']
clients_collection = db['clients']
leads_collection = db['leads']
faqs_collection = db['faqs']
admin_users_collection = db['admin_users']


# Chat model — override via OPENAI_CHAT_MODEL (e.g. "gpt-4o" for higher quality).
# Embeddings stay on OpenAI's default (text-embedding-ada-002) since the FAISS
# vectorstores were built with it — do NOT change the embedding model without re-embedding.
CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
llm = ChatOpenAI(temperature=0.3, model=CHAT_MODEL, request_timeout=30)

# In-memory caches
_session_memory: dict[str, any] = {}
_vectorstore_cache = {}
_config_cache = {}