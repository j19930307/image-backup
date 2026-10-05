from __future__ import annotations

import argparse
import json
import subprocess
import sys
import re
from pathlib import Path

from scrape_blog_posts import DEFAULT_BLOG_URL, scrape_all_posts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh blog_posts.json and back up only new posts.")
    parser.add_argument("--url", default=DEFAULT_BLOG_URL, help="Blog listing URL.")
    parser.add_argument("--json", default="blog_posts.json", help="Tracked blog posts JSON file.")
    parser.add_argument(
        "--skip-backup",
        action="store_true",
        help="Only refresh blog_posts.json. Do not run Google Drive backup.",
    )
    parser.add_argument(
        "--sync-notion",
        action="store_true",
        help="Sync blog_posts.json to Notion after backup.",
    )
    return parser.parse_args()


def load_existing_posts(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save_posts(path: Path, posts: list[dict[str, object]]) -> None:
    path.write_text(json.dumps(posts, ensure_ascii=False, indent=2), encoding="utf-8")


def normalized_title(value: object) -> str:
    return re.sub(r"\s+", " ", str(value).replace("\u00a0", " ")).strip().lower().replace("assemle", "assemble")


def merge_posts(existing: list[dict[str, object]], scraped: list[dict[str, object]]) -> tuple[list[dict[str, object]], int]:
    merged = [dict(post) for post in existing]
    existing_by_new_url = {str(post.get("new_url") or post.get("url")): post for post in merged}
    existing_by_title = {normalized_title(post.get("title")): post for post in merged}
    new_count = 0

    for scraped_post in scraped:
        url = str(scraped_post["url"])
        post = existing_by_new_url.get(url) or existing_by_title.get(normalized_title(scraped_post.get("title")))
        if post is not None:
            post["new_url"] = url
            continue

        post = dict(scraped_post)
        merged.append(post)
        existing_by_new_url[url] = post
        existing_by_title[normalized_title(post.get("title"))] = post
        new_count += 1

    return merged, new_count


def main() -> None:
    args = parse_args()
    repo_dir = Path(__file__).resolve().parent
    json_path = Path(args.json)
    if not json_path.is_absolute():
        json_path = repo_dir / json_path

    existing_posts = load_existing_posts(json_path)
    scraped_posts = scrape_all_posts(args.url)
    merged_posts, new_count = merge_posts(existing_posts, scraped_posts)
    save_posts(json_path, merged_posts)

    pending_count = sum(1 for post in merged_posts if not post.get("drive_folder_link"))

    print(f"Existing posts: {len(existing_posts)}")
    print(f"Scraped posts: {len(scraped_posts)}")
    print(f"New posts: {new_count}")
    print(f"Posts missing drive backup: {pending_count}")
    print(f"Updated: {json_path}")

    if pending_count == 0 or args.skip_backup:
        return

    subprocess.run(
        [sys.executable, str(repo_dir / "backup_blog_posts_to_drive.py")],
        check=True,
        cwd=repo_dir,
    )

    if args.sync_notion:
        subprocess.run(
            [sys.executable, str(repo_dir / "sync_blog_posts_to_notion.py")],
            check=True,
            cwd=repo_dir,
        )


if __name__ == "__main__":
    main()
