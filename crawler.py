"""Simple web scraper to fetch page titles."""

import sys
from urllib.request import urlopen
from html.parser import HTMLParser


class TitleParser(HTMLParser):
    """Parse the title of an HTML document."""

    def __init__(self):
        super().__init__()
        self.in_title = False
        self.title = None

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "title":
            self.in_title = True

    def handle_endtag(self, tag):
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title = data.strip()


def fetch_title(url: str) -> str | None:
    """Return the <title> of a web page, if available."""
    with urlopen(url) as response:
        html = response.read().decode("utf-8", "ignore")
    parser = TitleParser()
    parser.feed(html)
    return parser.title


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python crawler.py <url>")
        raise SystemExit(1)
    title = fetch_title(sys.argv[1])
    print(title or "No title found")
