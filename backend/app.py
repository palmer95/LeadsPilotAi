from flask import Flask, request, jsonify
from flask_cors import CORS
from langchain_openai import ChatOpenAI
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
import json
import sales_agent
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "http://localhost:3000"}}, supports_credentials=True)

embeddings = OpenAIEmbeddings()
vectorstore = FAISS.load_local("virtour_vectorstore", OpenAIEmbeddings(), allow_dangerous_deserialization=True)
llm = ChatOpenAI(temperature=0.3, model="gpt-3.5-turbo")
memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
qa = ConversationalRetrievalChain.from_llm(llm=llm, retriever=vectorstore.as_retriever(), memory=memory)

with open("client-configs/virtour_config.json") as f:
    CONFIG = json.load(f)

@app.route('/api/chat', methods=['POST', 'OPTIONS'])
def chat():
    if request.method == 'OPTIONS':
        response = app.make_response('')
        response.headers['Access-Control-Allow-Origin'] = 'http://localhost:3000'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response

    user_input = request.json.get('query').lower()

    # Special case: pricing inquiry — respond + begin sales flow
    if not sales_agent.is_active() and sales_agent.is_pricing_inquiry(user_input):
        return jsonify(sales_agent.handle_pricing_inquiry(CONFIG))


    if not sales_agent.is_active() and sales_agent.is_sales_trigger(user_input, CONFIG):
        return jsonify(sales_agent.start_sales_flow(CONFIG))

    if sales_agent.is_active():
        return jsonify(sales_agent.continue_sales_flow(user_input, CONFIG))

    try:
        result = qa.invoke({"question": user_input})
        response_text = result["answer"]

        fallback_phrases = [
            "i'm not sure",
            "i do not have that information",
            "i don't have specific information",
            "i don't have that info",
            "i don't know"
        ]

        if (not response_text.strip() or any(phrase in response_text.lower() for phrase in fallback_phrases)):
            gpt_direct = ChatOpenAI(temperature=0.3, model="gpt-3.5-turbo")
            fallback_prompt = f'''
You are Clyde 🤓, the AI assistant for {CONFIG["business_name"]}.
You help customers by answering questions and capturing lead details.
If someone asks your name, say “I’m Clyde, your friendly AI assistant.”

Business details:
{CONFIG["description"]}

User said:
\"\"\"{user_input}\"\"\"

Respond as Clyde.
            '''
            fallback = gpt_direct.invoke(fallback_prompt)
            response_text = "GPT: " + fallback.content

        return jsonify({ "response": response_text })

    except Exception as e:
        print("Error:", e)
        return jsonify({ "response": "Something went wrong processing your request." })

@app.route('/api/reset', methods=['POST'])
def reset():
    memory.clear()
    sales_agent.reset_sales_state()
    return jsonify({"message": "Chat history cleared."})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5050)
