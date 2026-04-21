from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

NOTION_VERSION = "2022-06-28"
DEFAULT_DATABASE_TITLE = "tripleS Blog Image Backups"
DEFAULT_TIME_ZONE = "Asia/Taipei"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create/sync a Notion database from blog_posts.json.")
    parser.add_argument("--input-json", default="blog_posts.json", help="Input blog_posts.json path.")
    parser.add_argument("--database-title", default=DEFAULT_DATABASE_TITLE, help="Database title when creating one.")
    return parser.parse_args()


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def notion_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }


def raise_for_notion_error(response: requests.Response) -> None:
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise RuntimeError(f"Notion API error {response.status_code}: {response.text}") from exc


def normalize_notion_id(raw_id: str) -> str:
    value = raw_id.strip()
    if "/" in value:
        value = value.rstrip("/").split("/")[-1]
    if "?" in value:
        value = value.split("?", 1)[0]
    if "-" in value:
        return value
    if len(value) == 32:
        return f"{value[:8]}-{value[8:12]}-{value[12:16]}-{value[16:20]}-{value[20:]}"
    return value


def load_posts(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def title_value(text: str) -> dict[str, list[dict[str, dict[str, str]]]]:
    return {"title": [{"text": {"content": text[:2000]}}]}


def rich_text_value(text: str | None) -> dict[str, list[dict[str, dict[str, str]]]]:
    if not text:
        return {"rich_text": []}
    return {"rich_text": [{"text": {"content": text[:2000]}}]}


def url_value(url: str | None) -> dict[str, str | None]:
    return {"url": url or None}


def number_value(value: Any) -> dict[str, int | float | None]:
    if value is None:
        return {"number": None}
    return {"number": int(value)}


def select_value(value: str | None) -> dict[str, dict[str, str] | None]:
    if not value:
        return {"select": None}
    return {"select": {"name": value}}


def date_value(value: str | None) -> dict[str, dict[str, str] | None]:
    if not value:
        return {"date": None}
    if re.search(r"(Z|[+-]\d{2}:\d{2})$", value):
        return {"date": {"start": value}}
    return {"date": {"start": value, "time_zone": DEFAULT_TIME_ZONE}}


def build_database_schema() -> dict[str, Any]:
    return {
        "Title": {"title": {}},
        "URL": {"url": {}},
        "Images": {"number": {"format": "number"}},
        "Drive Folder": {"url": {}},
        "Backup Finished": {"date": {}},
    }


def build_page_properties(post: dict[str, Any]) -> dict[str, Any]:
    return {
        "Title": title_value(str(post.get("title") or "")),
        "URL": url_value(post.get("url")),
        "Images": number_value(post.get("image_count")),
        "Drive Folder": url_value(post.get("drive_folder_link")),
        "Backup Finished": date_value(post.get("backup_finished_at")),
    }


def create_database(token: str, parent_page_id: str, title: str) -> str:
    response = requests.post(
        "https://api.notion.com/v1/databases",
        headers=notion_headers(token),
        json={
            "parent": {"type": "page_id", "page_id": normalize_notion_id(parent_page_id)},
            "title": [{"type": "text", "text": {"content": title}}],
            "properties": build_database_schema(),
        },
        timeout=30,
    )
    raise_for_notion_error(response)
    database_id = response.json()["id"]
    print(f"Created Notion database: {database_id}")
    print(f"Add this to .env: NOTION_DATABASE_ID={database_id}")
    return database_id


def update_database_schema(token: str, database_id: str) -> None:
    response = requests.patch(
        f"https://api.notion.com/v1/databases/{normalize_notion_id(database_id)}",
        headers=notion_headers(token),
        json={
            "properties": {
                **build_database_schema(),
            }
        },
        timeout=30,
    )
    raise_for_notion_error(response)


def query_existing_pages(token: str, database_id: str) -> dict[str, str]:
    pages_by_url: dict[str, str] = {}
    start_cursor: str | None = None

    while True:
        payload: dict[str, Any] = {"page_size": 100}
        if start_cursor:
            payload["start_cursor"] = start_cursor

        response = requests.post(
            f"https://api.notion.com/v1/databases/{normalize_notion_id(database_id)}/query",
            headers=notion_headers(token),
            json=payload,
            timeout=30,
        )
        raise_for_notion_error(response)
        body = response.json()

        for page in body.get("results", []):
            url_property = page.get("properties", {}).get("URL", {})
            url = url_property.get("url")
            if url:
                pages_by_url[url] = page["id"]

        if not body.get("has_more"):
            return pages_by_url
        start_cursor = body.get("next_cursor")


def create_page(token: str, database_id: str, post: dict[str, Any]) -> None:
    response = requests.post(
        "https://api.notion.com/v1/pages",
        headers=notion_headers(token),
        json={
            "parent": {"database_id": normalize_notion_id(database_id)},
            "properties": build_page_properties(post),
        },
        timeout=30,
    )
    raise_for_notion_error(response)


def update_page(token: str, page_id: str, post: dict[str, Any]) -> None:
    response = requests.patch(
        f"https://api.notion.com/v1/pages/{page_id}",
        headers=notion_headers(token),
        json={"properties": build_page_properties(post)},
        timeout=30,
    )
    raise_for_notion_error(response)


def main() -> None:
    args = parse_args()
    repo_dir = Path(__file__).resolve().parent
    input_path = Path(args.input_json)
    if not input_path.is_absolute():
        input_path = repo_dir / input_path

    token = require_env("NOTION_TOKEN")
    database_id = os.getenv("NOTION_DATABASE_ID")
    if not database_id:
        database_id = create_database(token, require_env("NOTION_PARENT_PAGE_ID"), args.database_title)
    else:
        update_database_schema(token, database_id)

    posts = load_posts(input_path)
    pages_by_url = query_existing_pages(token, database_id)
    created = 0
    updated = 0

    for index, post in enumerate(posts, start=1):
        url = str(post.get("url") or "")
        page_id = pages_by_url.get(url)
        if page_id:
            update_page(token, page_id, post)
            updated += 1
            print(f"[{index}/{len(posts)}] UPDATE {url}")
        else:
            create_page(token, database_id, post)
            created += 1
            print(f"[{index}/{len(posts)}] CREATE {url}")

    print(f"Synced {len(posts)} post(s). Created: {created}. Updated: {updated}.")


if __name__ == "__main__":
    main()
