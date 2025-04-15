import os
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from dotenv import load_dotenv

# Load environment variables (API keys, etc.)
load_dotenv()

openai_api_key = os.getenv("OPENAI_API_KEY")

# Read the scraped content
with open("virtour_content.txt", "r") as f:
    raw_text = f.read()

# Split the text into smaller chunks (for easier processing by the AI)
splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
chunks = splitter.split_text(raw_text)

# Generate embeddings for each chunk using OpenAI's API
embedding = OpenAIEmbeddings(openai_api_key=openai_api_key)

# Store the embeddings in FAISS (local database)
vectorstore = FAISS.from_texts(chunks, embedding)

# Save the FAISS vectorstore for later use
vectorstore.save_local("virtour_vectorstore")

print(f"✅ {len(chunks)} chunks embedded and saved to vectorstore.")
