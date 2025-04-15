from flask import Flask, request, jsonify
from flask_cors import CORS
from langchain_openai import ChatOpenAI
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

from dotenv import load_dotenv
load_dotenv()

# Setup
app = Flask(__name__)

# Enable CORS globally for all routes and for specific origins
CORS(app, resources={r"/api/*": {"origins": "http://localhost:3000"}}, supports_credentials=True)  # Enable CORS for React app

# Load the vectorstore and chain
embeddings = OpenAIEmbeddings()

# vectorstore = FAISS.load_local("virtour_vectorstore", embeddings)
vectorstore = FAISS.load_local(
    "virtour_vectorstore",
    OpenAIEmbeddings(),
    allow_dangerous_deserialization=True  # since we created the vectorstore ourselves
)

llm = ChatOpenAI(temperature=0.3, model="gpt-3.5-turbo")

# Add memory
memory = ConversationBufferMemory(
    memory_key="chat_history", 
    return_messages=True
)

qa = ConversationalRetrievalChain.from_llm(
    llm=llm,
    retriever=vectorstore.as_retriever(),
    memory=memory
)

@app.route('/api/chat', methods=['POST', 'OPTIONS'])
def chat():
    print(request)
    if request.method == 'OPTIONS':
        # CORS preflight request
        print("Received OPTIONS request - Preflight")
        response = app.make_response('')
        response.headers['Access-Control-Allow-Origin'] = 'http://localhost:3000'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response


    user_input = request.json.get('query')

    fallback_phrases = [
    "i'm not sure",
    "i do not have that information",
    "i don't have specific information",
    "i don't have that info"
    ]

    try:
        result = qa.invoke({"question": user_input})
        response_text = result["answer"]

        # fallback condition: vague / no answer / hallucination
        if (not response_text.strip() or any(phrase in response_text.lower() for phrase in fallback_phrases)):
            print("No good vector result — falling back to GPT")
            gpt_direct = ChatOpenAI(temperature=0.3, model="gpt-3.5-turbo")  # or gpt-3.5-turbo
            fallback_prompt = f"""
            Virtour Media is a photography and virtual tour service based in Santa Barbara. 
            They offer services such as real estate photography, Matterport 3D tours, aerial photos, before/after shots, virtual staging, and more. 
            They pride themselves on quality, fast turnaround, and helping businesses stand out visually.

            A user asked the following question:
            \"\"\"{user_input}\"\"\"

            Answer as if you are Virtour Media, being helpful and professional.
            """

            fallback = gpt_direct.invoke(fallback_prompt)
            response_text = "GPT: " + fallback.content


        return jsonify({ "response": response_text })

    except Exception as e:
        print("Error:", e)
        return jsonify({ "response": "Something went wrong processing your request." })

@app.route('/api/reset', methods=['POST'])
def reset():
    memory.clear()
    return jsonify({"message": "Chat history cleared."})



if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5050)
