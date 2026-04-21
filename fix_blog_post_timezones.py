from __future__ import annotations

import json
import re
from pathlib import Path

TIMEZONE_SUFFIX = "+08:00"
DATE_WITH_ZONE_PATTERN = re.compile(r"(Z|[+-]\d{2}:\d{2})$")


def main() -> None:
    path = Path(__file__).resolve().parent / "blog_posts.json"
    posts = json.loads(path.read_text(encoding="utf-8-sig"))
    changed = 0

    for post in posts:
        for key in ("backup_started_at", "backup_finished_at"):
            value = post.get(key)
            if isinstance(value, str) and value and not DATE_WITH_ZONE_PATTERN.search(value):
                post[key] = f"{value}{TIMEZONE_SUFFIX}"
                changed += 1

    if changed:
        path.write_text(json.dumps(posts, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"updated_time_fields={changed}")


if __name__ == "__main__":
    main()
