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
DEFAULT_BLOG_URL = "https://www.triplescosmos.com/"
PUBLISHING_KIT_API_URL = "https://api.publishingkit.net"
PUBLISHING_KIT_CHANNEL_CODE = "L2NoYW5uZWxzLzIyODk2"
PUBLISHING_KIT_CHANNEL_ID = "22896"
PUBLISHING_KIT_CONSUMER_ID = "PUBL-22896-B00001-129732"


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


def extract_api_image_urls(content: str) -> list[str]:
    soup = BeautifulSoup(content, "html.parser")
    return list(dict.fromkeys(img["src"].strip() for img in soup.select("img[src]") if img["src"].strip()))


def extract_api_posts(payload: dict[str, object]) -> list[dict[str, object]]:
    data = payload.get("data", [])
    if isinstance(data, list):
        return [post for post in data if isinstance(post, dict)]
    if isinstance(data, dict):
        for key in ("posts", "results"):
            posts = data.get(key, [])
            if isinstance(posts, list):
                return [post for post in posts if isinstance(post, dict)]
    return []


def fetch_current_posts(site_url: str = "https://www.triplescosmos.com/") -> list[dict[str, object]]:
    session = requests.Session()
    parsed_site_url = urlparse(site_url)
    site_root = f"{parsed_site_url.scheme}://{parsed_site_url.netloc}"
    base_headers = {
        "Origin": site_root,
        "Referer": f"{site_root}/",
        "User-Agent": USER_AGENT,
        "x-publ-channel-id": PUBLISHING_KIT_CHANNEL_ID,
    }
    check_in = session.post(
        f"{PUBLISHING_KIT_API_URL}/api/v2/channels/{PUBLISHING_KIT_CHANNEL_CODE}/guest-check-in",
        headers=base_headers,
        json={},
        timeout=30,
    )
    check_in.raise_for_status()
    check_in_payload = check_in.json()
    check_in_data = check_in_payload.get("data", {}) if isinstance(check_in_payload, dict) else {}
    token = (
        check_in_payload.get("token")
        or check_in_payload.get("accessToken")
        or (check_in_data.get("token") if isinstance(check_in_data, dict) else None)
    )
    if not token:
        raise RuntimeError("PublishingKit guest check-in did not return an access token.")

    headers = {
        **base_headers,
        "Authorization": f"Bearer {token}",
        "x-publ-consumer-id": PUBLISHING_KIT_CONSUMER_ID,
    }
    posts: list[dict[str, object]] = []
    for page in range(1, 1000):
        response = session.get(
            f"{PUBLISHING_KIT_API_URL}/api/v1/posts",
            params={"limit": 100, "page": page},
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        page_posts = extract_api_posts(response.json())
        posts.extend(page_posts)
        if len(page_posts) < 100:
            break

    discovered: list[dict[str, object]] = []
    seen_urls: set[str] = set()
    for post in posts:
        post_meta = post.get("postMeta", {})
        if not isinstance(post_meta, dict):
            continue
        canonical_url = str(post_meta.get("canonicalUrl") or "").replace(
            "https://app.publr.co", site_root,
        )
        title = normalize_text(str(post.get("title") or ""))
        if not title or not canonical_url or canonical_url in seen_urls:
            continue
        seen_urls.add(canonical_url)
        discovered.append(
            {
                "title": title,
                "url": canonical_url,
                "new_url": canonical_url,
                "image_urls": extract_api_image_urls(str(post.get("content") or "")),
            }
        )
    return discovered


def scrape_all_posts(start_url: str) -> list[dict[str, str]]:
    return fetch_current_posts(start_url)


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
