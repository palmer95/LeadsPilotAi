# Virtour AI Chatbot 🤖

An AI-powered chatbot built with:

- 💬 React frontend
- 🧠 Flask + LangChain backend
- 📚 FAISS vectorstore for local knowledge
- 🔍 OpenAI GPT-4 Turbo for intelligent responses

## Features

- Instant answers from VirtourMedia content
- Smooth chat interface
- Auto-scroll, loading states, and reset
- Built-in vector search (custom documents)
- More features coming soon:
  - Chat memory 🧠
  - Web search fallback 🌐
  - File uploads 📄

## Getting Started

1. Clone the repo
2. Create a `.env` file in the backend with your OpenAI key
3. Run the Python backend:
   ```bash
   cd backend
   source venv/bin/activate  # or venv\\Scripts\\activate for Windows
   python app.py
