#!/usr/bin/env python3
"""
ChainDocs crawler & embed pipeline
──────────────────────────────────
Usage:
    python crawler.py crawl      # scrape OpenZeppelin + EIP docs into docs.db
    python crawler.py embed      # chunk+embed pages and upload to Qdrant
"""

import argparse
import os
import sqlite3
import uuid
from typing import List

# ────────────── Scrapy imports (only needed for `crawl`) ──────────────
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from scrapy.crawler import CrawlerProcess
from scrapy.spiders import Spider

# ────────────── Embedding & vector store imports (for `embed`) ─────────
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer

# ------------------------------ CONSTANTS ------------------------------
START_URLS = [
    "https://docs.openzeppelin.com/contracts/5.x/",
    "https://eips.ethereum.org/",
]
SQLITE_DB = "docs.db"
COLLECTION = os.getenv("QDRANT_COLLECTION", "chaindocs")
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
MAX_TOKENS = 512
TOKEN_OVERLAP = 50

# ========================= 1. SCRAPY CRAWLER ===========================
class SQLitePipeline:
    def open_spider(self, spider):
        self.conn = sqlite3.connect(SQLITE_DB)
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS pages "
            "(id INTEGER PRIMARY KEY, title TEXT, url TEXT UNIQUE, body TEXT)"
        )

    def close_spider(self, spider):
        self.conn.close()

    def process_item(self, item, spider):
        self.conn.execute(
            "INSERT OR REPLACE INTO pages(title, url, body) VALUES (?,?,?)",
            (item["title"], item["url"], item["body"]),
        )
        self.conn.commit()
        return item


class DocsSpider(Spider):
    name = "docs"
    start_urls = START_URLS
    allowed_domains = [
        "docs.openzeppelin.com",
        "eips.ethereum.org",
        "openzeppelin.com",
        "ethereum.org",
    ]

    def parse(self, response):
        if b"text/html" not in response.headers.get("Content-Type", b""):
            return

        soup = BeautifulSoup(response.text, "html.parser")
        # Drop nav bars / sidebars
        for nav in soup.find_all("nav"):
            nav.decompose()

        title = soup.title.string.strip() if soup.title else ""
        canonical = soup.find("link", rel="canonical")
        url = canonical["href"].strip() if canonical and canonical.get("href") else response.url
        body_md = md(str(soup.body)) if soup.body else ""

        yield {"title": title, "url": url, "body": body_md}

        # Follow in-site links
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("#") or href.startswith("mailto:"):
                continue
            nxt = response.urljoin(href)
            if any(nxt.startswith(u) for u in START_URLS):
                yield response.follow(nxt, callback=self.parse)


def run_crawler():
    process = CrawlerProcess(
        settings={
            "ITEM_PIPELINES": {f"{__name__}.SQLitePipeline": 300},
            "LOG_LEVEL": "INFO",
        }
    )
    process.crawl(DocsSpider)
    process.start()


# ========================= 2. CHUNK + EMBED ============================
def _chunk(text: str, tokenizer: AutoTokenizer) -> List[str]:
    ids = tokenizer.encode(text, add_special_tokens=False)
    step = MAX_TOKENS - TOKEN_OVERLAP
    return [
        tokenizer.decode(ids[i : i + MAX_TOKENS])
        for i in range(0, len(ids), step)
    ]


def run_embed():
    # --- read pages -----------------------------------------------------
    db = sqlite3.connect(SQLITE_DB)
    rows = db.execute("SELECT id, body FROM pages").fetchall()
    if not rows:
        print("No pages found in docs.db. Run `crawl` first.")
        return

    # --- init models ----------------------------------------------------
    emb_model = SentenceTransformer(EMBED_MODEL)
    tokenizer = AutoTokenizer.from_pretrained(EMBED_MODEL)

    client = QdrantClient(
        url=os.getenv("QDRANT_URL"),
        api_key=os.getenv("QDRANT_API_KEY"),
    )

    # ensure collection exists
    client.recreate_collection(
        collection_name=COLLECTION,
        vectors_config=qmodels.VectorParams(size=emb_model.get_sentence_embedding_dimension(),
                                            distance=qmodels.Distance.COSINE),
    )

    # --- iterate pages --------------------------------------------------
    for page_id, body in rows:
        for chunk in _chunk(body, tokenizer):
            vec = emb_model.encode(chunk).tolist()
            point = qmodels.PointStruct(
                id=str(uuid.uuid4()),
                vector=vec,
                payload={"doc_id": page_id, "text": chunk},
            )
            client.upsert(collection_name=COLLECTION, points=[point])

    print("✅ Uploaded embeddings to Qdrant")


# ============================= CLI ENTRY ===============================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ChainDocs crawler & embedder")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("crawl", help="Scrape docs into SQLite")
    sub.add_parser("embed", help="Chunk, embed & upload to Qdrant")

    args = parser.parse_args()

    if args.cmd == "crawl":
        run_crawler()
    elif args.cmd == "embed":
        run_embed()
    else:
        parser.print_help()
