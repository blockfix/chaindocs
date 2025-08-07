codex/create-crawler.py-with-scrapy
import argparse
import sqlite3

from bs4 import BeautifulSoup
from markdownify import markdownify as md
from scrapy.crawler import CrawlerProcess
from scrapy.spiders import Spider


START_URLS = [
    'https://docs.openzeppelin.com/contracts/5.x/',
    'https://eips.ethereum.org/',
]


class SQLitePipeline:
    def open_spider(self, spider):
        self.conn = sqlite3.connect('docs.db')
        self.conn.execute(
            'CREATE TABLE IF NOT EXISTS pages (id INTEGER PRIMARY KEY, title TEXT, url TEXT UNIQUE, body TEXT)'
        )

    def close_spider(self, spider):
        self.conn.close()

    def process_item(self, item, spider):
        self.conn.execute(
            'INSERT OR REPLACE INTO pages(title, url, body) VALUES (?, ?, ?)',
            (item['title'], item['url'], item['body']),
        )
        self.conn.commit()
        return item


class DocsSpider(Spider):
    name = 'docs'
    start_urls = START_URLS
    allowed_domains = ['docs.openzeppelin.com', 'eips.ethereum.org', 'openzeppelin.com', 'ethereum.org']

    def parse(self, response):
        content_type = response.headers.get('Content-Type', b'').decode('utf-8')
        if 'text/html' not in content_type and 'application/xhtml+xml' not in content_type:
            return

        soup = BeautifulSoup(response.text, 'html.parser')
        for nav in soup.find_all('nav'):
            nav.decompose()

        title = ''
        if soup.title and soup.title.string:
            title = soup.title.string.strip()

        canonical = soup.find('link', rel='canonical')
        canonical_url = canonical['href'].strip() if canonical and canonical.get('href') else response.url

        body = ''
        if soup.body:
            body = md(str(soup.body))

        yield {'title': title, 'url': canonical_url, 'body': body}

        for a in soup.find_all('a', href=True):
            href = a['href']
            if href.startswith('mailto:') or href.startswith('#'):
                continue
            url = response.urljoin(href)
            if any(url.startswith(u) for u in START_URLS):
                yield response.follow(url, callback=self.parse)


def main():
    parser = argparse.ArgumentParser(description='Docs crawler')
    parser.add_argument('command', choices=['crawl'])
    args = parser.parse_args()

    if args.command == 'crawl':
        process = CrawlerProcess(settings={
            'ITEM_PIPELINES': {f'{__name__}.SQLitePipeline': 300},
            'LOG_LEVEL': 'INFO',
        })
        process.crawl(DocsSpider)
        process.start()


if __name__ == '__main__':
    main()
=======
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
 main
