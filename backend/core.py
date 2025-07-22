import os
from pymongo import MongoClient
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

# Initialize core services to be shared
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
db = client['leadsPilotAI']

#collections
conversations_collection = db['conversations']
clients_collection = db['clients']
leads_collection = db['leads']
faqs_collection = db['faqs']
admin_users_collection = db['admin_users']


llm = ChatOpenAI(temperature=0.3, model="gpt-3.5-turbo", request_timeout=30)

# In-memory caches
_session_memory: dict[str, any] = {}
_vectorstore_cache = {}
_config_cache = {}