import os
import sqlite3
import uuid
import argparse
from typing import List

from qdrant_client import QdrantClient
from qdrant_client.http import models
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer


def crawl() -> None:
    """Placeholder crawl command."""
    print("crawl command not implemented")


def _chunk_text(tokenizer: AutoTokenizer, text: str, max_tokens: int = 512, overlap: int = 50) -> List[str]:
    token_ids = tokenizer.encode(text, add_special_tokens=False)
    step = max_tokens - overlap
    chunks: List[str] = []
    for start in range(0, len(token_ids), step):
        chunk_ids = token_ids[start:start + max_tokens]
        chunks.append(tokenizer.decode(chunk_ids))
    return chunks


def embed() -> None:
    db = sqlite3.connect("docs.db")
    cursor = db.cursor()
    cursor.execute("SELECT id, body FROM docs")
    rows = cursor.fetchall()

    model_name = "sentence-transformers/all-MiniLM-L6-v2"
    model = SentenceTransformer(model_name)
    tokenizer = AutoTokenizer.from_pretrained(model_name)

    qdrant_url = os.environ["QDRANT_URL"]
    qdrant_api_key = os.environ["QDRANT_API_KEY"]
    client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)

    for doc_id, body in rows:
        chunks = _chunk_text(tokenizer, body)
        vectors = model.encode(chunks)
        points = [
            models.PointStruct(
                id=str(uuid.uuid4()),
                vector=vector.tolist(),
                payload={"doc_id": doc_id, "text": chunk},
            )
            for vector, chunk in zip(vectors, chunks)
        ]
        client.upsert(collection_name="docs", points=points)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("crawl")
    sub.add_parser("embed")
    args = parser.parse_args()

    if args.command == "crawl":
        crawl()
    elif args.command == "embed":
        embed()
    else:
        parser.print_help()
