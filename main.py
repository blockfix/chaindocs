from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import List, Tuple

import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
from llama_cpp import Llama

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

BASE_DIR = Path(__file__).resolve().parent
INDEX_PATH = BASE_DIR / "index.html"

EMBED_MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDER = SentenceTransformer(EMBED_MODEL_NAME)

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "chaindocs")

TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")
MODEL_PATH = "models/llama-2-7b-q4.bin"

llm: Llama | None = None
llm_lock = threading.Lock()

qdrant: QdrantClient | None = None
if QDRANT_URL and QDRANT_API_KEY:
    try:
        qdrant = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    except Exception:
        qdrant = None


async def _get_query(req: Request) -> str:
    """Read 'query' from JSON or form; also accept 'message' as alias."""
    ct = (req.headers.get("content-type") or "").lower()
    query = ""
    if "application/json" in ct:
        body = await req.json()
        query = (body.get("query") or body.get("message") or "").strip()
    else:
        form = await req.form()
        query = (form.get("query") or form.get("message") or "").strip()
    return query


def _search_qdrant(query_vec: List[float]) -> Tuple[List[str], List[str]]:
    """Return (context_chunks, sources). If qdrant not configured, both empty."""
    if not qdrant:
        return [], []
    try:
        hits = qdrant.search(
            collection_name=QDRANT_COLLECTION,
            query_vector=query_vec,
            limit=5,
            with_payload=True,
        )
    except Exception:
        # collection might not exist yet, or Qdrant creds invalid
        return [], []

    chunks, sources = [], []
    for h in hits:
        payload = h.payload or {}
        text = payload.get("text") or payload.get("page_content") or ""
        if text:
            chunks.append(text)
        src = payload.get("url") or payload.get("source")
        if src:
            sources.append(src)
    return chunks, sources


def _answer_with_llm(prompt: str) -> str:
    """Try local llama.cpp first; fall back to Together AI."""
    if llm:
        with llm_lock:
            out = llm(prompt, max_tokens=512, stop=["</s>"])
        return out["choices"][0]["text"].strip()

    if not TOGETHER_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="No local model and TOGETHER_API_KEY not set"
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
    return (
        resp.json()
        .get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
        .strip()
    )


@app.get("/", response_class=HTMLResponse)
async def spa() -> HTMLResponse:
    """Serve the glass UI (index.html)."""
    if not INDEX_PATH.exists():
        raise HTTPException(status_code=500, detail="index.html not found")
    return HTMLResponse(INDEX_PATH.read_text(encoding="utf-8"))


@app.post("/ask")
async def ask(req: Request):
    """RAG endpoint: embed → search Qdrant → LLM answer.
       Returns HTML snippet for HTMX requests, JSON otherwise.
    """
    query = await _get_query(req)
    if not query:
        raise HTTPException(status_code=400, detail="Query is empty")

    global llm
    if llm is None and os.path.exists(MODEL_PATH):
        with llm_lock:
            if llm is None:
                llm = Llama(model_path=MODEL_PATH, n_ctx=4096)

    # Embed & retrieve
    query_vec = EMBEDDER.encode(query).tolist()
    chunks, sources = _search_qdrant(query_vec)
    context = "\n\n".join(chunks)

    prompt = (
        "Use the following context to answer the question.\n\n"
        f"{context}\n\nQuestion: {query}\nAnswer:"
    )
    answer = _answer_with_llm(prompt)

    # HTMX? Return HTML bubble; else JSON (for CLI)
    if req.headers.get("HX-Request"):
        html = (
            f'<div class="md space-y-1">'
            f'<div class="text-indigo-300 text-sm">You</div>'
            f'<div class="mb-3">{query}</div>'
            f'<div class="text-indigo-300 text-sm">Answer</div>'
            f'<div>{answer}</div>'
            f'<div class="text-indigo-300 text-sm mt-2">Sources</div>'
            + "".join(f'<div class="text-indigo-200/80">• {s}</div>' for s in sources)
            + "</div>"
        )
        return HTMLResponse(html)

    return JSONResponse({"answer": answer, "sources": sources})


HEALTH_STATUS_MSG = os.getenv("HEALTH_STATUS_MSG", "ChainDocs API is alive!")


@app.get("/health")
def health():
    return {
        "status": HEALTH_STATUS_MSG,
        "embedder": EMBED_MODEL_NAME,
        "qdrant_configured": bool(qdrant),
        "collection": QDRANT_COLLECTION,
    }
