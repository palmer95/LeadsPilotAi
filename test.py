try:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain.embeddings import OpenAIEmbeddings
    from langchain.vectorstores import FAISS
    from dotenv import load_dotenv
    print("All imports are working!")
except ImportError as e:
    print(f"Error with import: {e}")
