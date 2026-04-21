from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
)
DEFAULT_BLOG_URL = "https://www.triplescosmos.com/blog"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape all tripleS blog post titles and links.")
    parser.add_argument("--url", default=DEFAULT_BLOG_URL, help="Blog listing URL.")
    parser.add_argument(
        "--output-csv",
        default="blog_posts.csv",
        help="CSV output path.",
    )
    parser.add_argument(
        "--output-json",
        default="blog_posts.json",
        help="JSON output path.",
    )
    return parser.parse_args()


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def fetch_html(session: requests.Session, url: str) -> str:
    response = session.get(url, timeout=30)
    response.raise_for_status()
    return response.text


def is_post_url(blog_url: str, href: str) -> bool:
    absolute = urljoin(blog_url, href)
    parsed = urlparse(absolute)
    if parsed.netloc != urlparse(blog_url).netloc:
        return False
    if not parsed.path.startswith("/blog/"):
        return False
    if parsed.path.rstrip("/") == "/blog":
        return False
    return True


def extract_posts(page_url: str, html: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    posts: list[tuple[str, str]] = []
    seen_urls: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        if not is_post_url(page_url, href):
            continue

        post_url = urljoin(page_url, href)
        title = normalize_text(anchor.get_text(" ", strip=True))
        if not title:
            continue

        if post_url in seen_urls:
            continue
        seen_urls.add(post_url)
        posts.append((post_url, title))

    return posts


def find_next_page(page_url: str, html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    for anchor in soup.find_all("a", href=True):
        text = normalize_text(anchor.get_text(" ", strip=True)).lower()
        if text == "next":
            return urljoin(page_url, anchor["href"])
    return None


def extract_post_title(html: str, fallback: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        return normalize_text(og_title["content"])

    title_tag = soup.find("title")
    if title_tag:
        title_text = normalize_text(title_tag.get_text(" ", strip=True))
        if title_text:
            return title_text.removesuffix(" | tripleS")

    heading = soup.find(["h1", "h2"])
    if heading:
        heading_text = normalize_text(heading.get_text(" ", strip=True))
        if heading_text:
            return heading_text

    return fallback


def scrape_all_posts(start_url: str) -> list[dict[str, str]]:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    discovered_posts: list[tuple[str, str]] = []
    seen_post_urls: set[str] = set()
    visited_pages: set[str] = set()
    next_url: str | None = start_url

    while next_url and next_url not in visited_pages:
        visited_pages.add(next_url)
        html = fetch_html(session, next_url)
        page_posts = extract_posts(next_url, html)
        for post_url, title in page_posts:
            if post_url in seen_post_urls:
                continue
            seen_post_urls.add(post_url)
            discovered_posts.append((post_url, title))
        next_url = find_next_page(next_url, html)

    posts: list[dict[str, str]] = []
    for url, title in reversed(discovered_posts):
        try:
            post_html = fetch_html(session, url)
            clean_title = extract_post_title(post_html, title)
        except requests.RequestException:
            clean_title = title
        posts.append({"title": clean_title, "url": url})
    return posts


def write_csv(output_path: Path, posts: list[dict[str, str]]) -> None:
    with output_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=["title", "url"])
        writer.writeheader()
        writer.writerows(posts)


def write_json(output_path: Path, posts: list[dict[str, str]]) -> None:
    output_path.write_text(json.dumps(posts, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    repo_dir = Path(__file__).resolve().parent
    posts = scrape_all_posts(args.url)

    csv_path = Path(args.output_csv)
    json_path = Path(args.output_json)
    if not csv_path.is_absolute():
        csv_path = repo_dir / csv_path
    if not json_path.is_absolute():
        json_path = repo_dir / json_path

    write_csv(csv_path, posts)
    write_json(json_path, posts)

    print(f"Found {len(posts)} posts")
    print(f"CSV: {csv_path}")
    print(f"JSON: {json_path}")
    for post in posts[:10]:
        line = f"- {post['title']} -> {post['url']}"
        print(line.encode("cp950", errors="replace").decode("cp950"))


if __name__ == "__main__":
    main()
