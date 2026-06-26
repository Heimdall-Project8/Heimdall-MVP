import os
from dotenv import load_dotenv

from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

load_dotenv()

DATA_FOLDER = "data/documents"
CHROMA_PATH = "chroma_db"

embedding_model = HuggingFaceEmbeddings(
    model_name="BAAI/bge-small-en-v1.5"
)

splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=100
)

documents = []

for file in os.listdir(DATA_FOLDER):

    if file.endswith(".pdf"):

        path = os.path.join(DATA_FOLDER, file)

        loader = PyMuPDFLoader(path)

        docs = loader.load()

        for d in docs:
            d.metadata["source"] = file

        documents.extend(docs)

chunks = splitter.split_documents(documents)

print(f"Created {len(chunks)} chunks")

vector_db = Chroma.from_documents(
    documents=chunks,
    embedding=embedding_model,
    persist_directory=CHROMA_PATH
)

print("Indexing Complete!")