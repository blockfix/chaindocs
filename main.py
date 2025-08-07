codex/implement-real-/ask-functionality-in-main.py
"""FastAPI application exposing a simple QA endpoint."""

from __future__ import annotations

import os
from typing import List

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
from llama_cpp import Llama

# main.py
from fastapi import FastAPI, Query

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer
from langchain.llms.fake import FakeListLLM
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
 main


app = FastAPI()


 codex/implement-real-/ask-functionality-in-main.py
# --- Models and Clients ----------------------------------------------------

# Embedder model used for transforming queries into vectors
_EMBEDDER = SentenceTransformer("all-MiniLM-L6-v2")

# Qdrant configuration with sensible defaults for local development
_qdrant_host = os.getenv("QDRANT_HOST", "localhost")
_qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
_qdrant_collection = os.getenv("QDRANT_COLLECTION", "chaindocs")
_qdrant = QdrantClient(host=_qdrant_host, port=_qdrant_port)

_model_path = "models/llama-2-7b-q4.bin"


class AskRequest(BaseModel):
    """Schema for /ask requests."""

    query: str


class AskResponse(BaseModel):
    """Schema for /ask responses."""

    answer: str
    sources: List[str]

# Set up embedding model and in-memory vector store
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
qdrant = QdrantClient(":memory:")
qdrant.recreate_collection(
    collection_name="docs",
    vectors_config=VectorParams(size=384, distance=Distance.COSINE),
)

# Example documents for retrieval
documents = [
    "ChainDocs helps organize your documentation with retrieval augmented generation.",
    "RAG combines search and large language models to answer questions from context.",
]

points = [
    PointStruct(
        id=idx,
        vector=embedding_model.encode(text).tolist(),
        payload={"text": text},
    )
    for idx, text in enumerate(documents)
]
qdrant.upsert(collection_name="docs", points=points)

prompt = PromptTemplate(
    template=(
        "Use the context to answer the question.\n"
        "Context: {context}\n"
        "Question: {question}\n"
        "Answer:"
    ),
    input_variables=["context", "question"],
)

llm = FakeListLLM(responses=["I'm a mock model."])
chain = LLMChain(prompt=prompt, llm=llm)
 main


@app.get("/")
def root():
    """Simple heartbeat endpoint."""

    return {"status": "ChainDocs API is alive!"}


 codex/implement-real-/ask-functionality-in-main.py
@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    """Answer a question using document context and an LLM.

    The query is embedded with a SentenceTransformer model, the top-5
    documents are fetched from Qdrant, and the combined context is used to
    prompt a local Llama model if available or the Together AI API otherwise.
    """

    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query is empty")

    # Embed the query and search Qdrant for relevant context
    query_vector = _EMBEDDER.encode(query).tolist()
    search_result = _qdrant.search(
        collection_name=_qdrant_collection,
        query_vector=query_vector,
        limit=5,
        with_payload=True,
    )

    # Build context and collect sources
    context_parts: List[str] = []
    sources: List[str] = []
    for hit in search_result:
        payload = hit.payload or {}
        text = payload.get("text") or payload.get("page_content") or ""
        if text:
            context_parts.append(text)
        source = payload.get("source") or payload.get("url")
        if source:
            sources.append(source)

    context = "\n\n".join(context_parts)
    prompt = (
        "Use the following context to answer the question.\n\n"
        f"{context}\n\nQuestion: {query}\nAnswer:"
    )

    if os.path.exists(_model_path):
        # Local inference using llama.cpp
        llm = Llama(model_path=_model_path, n_ctx=4096)
        completion = llm(prompt, max_tokens=512, stop=["</s>"])
        answer = completion["choices"][0]["text"].strip()
    else:
        # Remote inference using Together AI
        api_key = os.getenv("TOGETHER_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="TOGETHER_API_KEY not set")

        response = requests.post(
            "https://api.together.xyz/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "meta-llama/Llama-2-7b-chat-hf",
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        answer = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )

    return AskResponse(answer=answer, sources=sources)

@app.get("/ask")
def ask(question: str = Query(..., description="Question to ask the knowledge base")):
    query_vector = embedding_model.encode(question).tolist()
    result = qdrant.search(
        collection_name="docs", query_vector=query_vector, limit=1
    )
    context = result[0].payload["text"] if result else ""
    answer = chain.invoke({"context": context, "question": question})["text"]
    return {"answer": answer, "context": context}

main
