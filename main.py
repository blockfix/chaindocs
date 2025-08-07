"""
ChainDocs FastAPI backend
─────────────────────────
• `/`          → serves the glass-morphism chat UI (index.html)
• `/ask` [POST]→ RAG endpoint  (expects {"query": "..."} JSON)
• `/health`    → simple heartbeat for uptime checks
"""

from __future__ import annotations

import os
from typing import List

import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
from llama_cpp import Llama
from pathlib import Path

# --------------------------------------------------------------------------- #
#  Init FastAPI app & static hosting
# --------------------------------------------------------------------------- #
ROOT = Path(__file__).resolve().parent

app = FastAPI()
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")

# --------------------------------------------------------------------------- #
#  Global models / clients
# --------------------------------------------------------------------------- #
EMBEDDER = SentenceTransformer("all-MiniLM-L6-v2")

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "chaindocs")

qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

MODEL_PATH = "models/llama-2-7b-q4.bin"  # local llama.cpp model
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")  # fallback key

# --------------------------------------------------------------------------- #
#  Pydantic schemas
# --------------------------------------------------------------------------- #
class AskRequest(BaseModel):
    query: str


class AskResponse(BaseModel):
    answer: str
    sources: List[str]


# --------------------------------------------------------------------------- #
#  Routes
# --------------------------------------------------------------------------- #
@app.get("/")
async def spa() -> FileResponse:
    """Serve the HTML chat UI."""
    return FileResponse(ROOT / "index.html")


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    """Answer a question using RAG over the Qdrant corpus."""
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query is empty")

    # 1. Embed query & vector-search Qdrant
    query_vec = EMBEDDER.encode(query).tolist()
    hits = qdrant.search(
        collection_name=QDRANT_COLLECTION,
        query_vector=query_vec,
        limit=5,
        with_payload=True,
    )

    context_chunks, sources = [], []
    for hit in hits:
        payload = hit.payload or {}
        text = payload.get("text") or payload.get("page_content") or ""
        if text:
            context_chunks.append(text)
        src = payload.get("url") or payload.get("source")
        if src:
            sources.append(src)

    context = "\n\n".join(context_chunks)
    prompt = (
        "Use the following context to answer the question.\n\n"
        f"{context}\n\nQuestion: {query}\nAnswer:"
    )

    # 2. Run LLM — local llama.cpp first, fallback to Together AI
    if os.path.exists(MODEL_PATH):
        llm = Llama(model_path=MODEL_PATH, n_ctx=4096)
        completion = llm(prompt, max_tokens=512, stop=["</s>"])
        answer = completion["choices"][0]["text"].strip()
    else:
        if not TOGETHER_API_KEY:
            raise HTTPException(
                status_code=500,
                detail="Neither local model nor TOGETHER_API_KEY is available",
            )
        resp = requests.post(
            "https://api.together.xyz/v1/chat/completions",
            headers={"Authorization": f"Bearer {TOGETHER_API_KEY}"},
            json={
                "model": "meta-llama/Llama-2-7b-chat-hf",
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=60,
        )
        resp.raise_for_status()
        answer = (
            resp.json()
            .get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )

    return AskResponse(answer=answer, sources=sources)


@app.get("/health")
def health():
    return {"status": "ChainDocs API is alive!"}
