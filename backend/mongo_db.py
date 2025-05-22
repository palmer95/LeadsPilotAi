from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

# Load MongoDB URI from .env
mongo_uri = os.getenv('MONGO_URI')

# Connect to MongoDB
client = MongoClient(mongo_uri)
db = client['leadsPilotAI']  # Use your database name

# Collections
clients_collection = db.clients
admin_users_collection = db.admin_users
leads_collection = db.leads
faq_collection = db.faqs
workflows_collection = db.workflows

# You can now use `clients_collection`, `admin_users_collection`, etc. in your routes
