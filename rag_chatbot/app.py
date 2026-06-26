import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_groq import ChatGroq

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

embedding_model = HuggingFaceEmbeddings(
    model_name="BAAI/bge-small-en-v1.5"
)

vector_db = Chroma(
    persist_directory="chroma_db",
    embedding_function=embedding_model
)

retriever = vector_db.as_retriever(
    search_kwargs={"k":3}
)

llm = ChatGroq(
    groq_api_key=os.getenv("GROQ_API_KEY"),
    model="llama-3.3-70b-versatile"
)


class ChatRequest(BaseModel):
    question: str


@app.post("/chat")
def chat(req: ChatRequest):

    docs = retriever.invoke(req.question)

    context = "\n\n".join([d.page_content for d in docs])

    prompt = f"""
You are Heimdall AI, an assistant for residents of a gated community.

Your job is to answer ONLY using the information provided in the context below.

Rules:
- Do NOT use outside knowledge.
- Do NOT guess.
- If the answer is not in the context, reply:
  "I couldn't find this information in the community handbook."
- Be concise and helpful.
- Do not mention policies that are not in the context.

Context:

{context}

Question:
{req.question}

"""

    response = llm.invoke(prompt)

    sources = []

    for d in docs:

        sources.append(
            {
                "document": d.metadata.get("source"),
                "page": d.metadata.get("page")
            }
        )

    return {
        "answer": response.content,
        "sources": sources
    }