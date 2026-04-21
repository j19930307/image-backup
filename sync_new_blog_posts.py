from __future__ import annotations

import argparse
import json
import subprocess
import sys
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
    return parser.parse_args()


def load_existing_posts(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save_posts(path: Path, posts: list[dict[str, object]]) -> None:
    path.write_text(json.dumps(posts, ensure_ascii=False, indent=2), encoding="utf-8")


def merge_posts(existing: list[dict[str, object]], scraped: list[dict[str, str]]) -> tuple[list[dict[str, object]], int]:
    existing_by_url = {str(post["url"]): post for post in existing}
    merged: list[dict[str, object]] = []
    new_count = 0

    for scraped_post in scraped:
        url = scraped_post["url"]
        if url in existing_by_url:
            post = existing_by_url[url]
            post["title"] = scraped_post["title"]
        else:
            post = dict(scraped_post)
            new_count += 1
        merged.append(post)

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

    print(f"Existing posts: {len(existing_posts)}")
    print(f"Scraped posts: {len(scraped_posts)}")
    print(f"New posts: {new_count}")
    print(f"Updated: {json_path}")

    if new_count == 0 or args.skip_backup:
        return

    subprocess.run(
        [sys.executable, str(repo_dir / "backup_blog_posts_to_drive.py")],
        check=True,
        cwd=repo_dir,
    )


if __name__ == "__main__":
    main()
