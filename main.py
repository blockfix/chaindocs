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


app = FastAPI()


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


@app.get("/")
def root():
    """Simple heartbeat endpoint."""

    return {"status": "ChainDocs API is alive!"}


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
