import argparse
import requests

DEFAULT_HOST = "http://localhost:8000"


def color(text: str, code: str) -> str:
    """Return text string wrapped in ANSI color codes."""
    return f"\033[{code}m{text}\033[0m"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Query the ChainDocs API via the /ask endpoint"
    )
    parser.add_argument("query", help="Question to send to the API")
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help="Base URL for the ChainDocs API (default: %(default)s)",
    )
    args = parser.parse_args()

    try:
        response = requests.get(f"{args.host}/ask", params={"question": args.query})
        response.raise_for_status()
        data = response.json()
        answer = data.get("answer", "")
        context = data.get("context", "")
        print(color("Answer:", "1;32"), answer)
        print(color("Context:", "1;34"), context)
    except Exception as exc:  # broad catch to surface connection errors nicely
        print(color("Error:", "1;31"), exc)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
