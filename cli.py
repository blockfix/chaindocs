#!/usr/bin/env python3
"""
ChainDocs CLI
─────────────
Ask your deployed ChainDocs API a question from the terminal:

    python -m cli "What is an ERC20 token?"
    python -m cli "How to pause an ERC20?" --host https://chaindocs.onrender.com
"""

import argparse
import json
import sys
from typing import List

import requests

DEFAULT_HOST = "http://localhost:8000"  # override with --host for Render URL


def color(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m"


def pretty_sources(srcs: List[str]) -> str:
    return "\n".join(f"  – {s}" for s in srcs) if srcs else "  (none)"


def main() -> None:
    parser = argparse.ArgumentParser(description="Query the ChainDocs /ask endpoint")
    parser.add_argument("query", help="Question to send to the API")
    parser.add_argument("--host", default=DEFAULT_HOST,
                        help="Base URL for the ChainDocs API (default: %(default)s)")
    args = parser.parse_args()

    try:
        resp = requests.post(f"{args.host}/ask", json={"query": args.query}, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        print(color("\nAnswer", "1;32"))
        print(data.get("answer", "(no answer returned)"))

        print(color("\nSources", "1;34"))
        print(pretty_sources(data.get("sources", [])))

    except requests.RequestException as exc:
        print(color("Network / API error:", "1;31"), exc)
        sys.exit(1)
    except json.JSONDecodeError:
        print(color("Invalid JSON received from API.", "1;31"))
        sys.exit(1)


if __name__ == "__main__":
    main()
