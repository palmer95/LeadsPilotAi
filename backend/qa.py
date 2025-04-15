import os
from dotenv import load_dotenv
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from langchain.chat_models import ChatOpenAI
from langchain.chains.question_answering import load_qa_chain
from langchain.prompts import PromptTemplate

load_dotenv()

# Load vectorstore and embedding model
embedding = OpenAIEmbeddings(openai_api_key=os.getenv("OPENAI_API_KEY"))
#print("Loading vectorstore...")
vectorstore = FAISS.load_local(
    "virtour_vectorstore",
    OpenAIEmbeddings(),
    allow_dangerous_deserialization=True
)
#print("Vectorstore loaded.")


# Load GPT model
#print("Initializing LLM...")
llm = ChatOpenAI(model_name="gpt-3.5-turbo", temperature=0, openai_api_key=os.getenv("OPENAI_API_KEY"))
#print("LLM ready.")


# Load QA chain
#print("Loading QA chain...")
qa_chain = load_qa_chain(llm, chain_type="stuff")
#print("QA chain ready.")

# Ask questions in a loop
if __name__ == "__main__":
    print("🤖 Ask me anything about VirtourMedia! (type 'exit' to quit)")
    while True:
        query = input("\nYou: ")
        if query.lower() in ["exit", "quit"]:
            break

        # Retrieve relevant chunks
        docs = vectorstore.similarity_search(query)

        # Get answer from GPT
        #response = qa_chain.run(input_documents=docs, question=query)
        response = qa_chain.invoke({"input_documents": docs, "question": query})
        answer = response['output_text']
        print(f"Bot: {answer}")
