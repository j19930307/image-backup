from __future__ import annotations

import argparse
from pathlib import Path

from backup_core import DEFAULT_DRIVE_FOLDER, DEFAULT_URL, backup_images


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download all images from a tripleS Cosmos blog page and upload them to Google Drive."
    )
    parser.add_argument("--url", default=DEFAULT_URL, help="Blog page URL.")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Local output directory. Defaults to downloads/<page slug>.",
    )
    parser.add_argument(
        "--drive-folder-name",
        default=DEFAULT_DRIVE_FOLDER,
        help="Target Google Drive folder name.",
    )
    parser.add_argument(
        "--drive-parent-id",
        default=None,
        help="Optional Google Drive parent folder ID.",
    )
    parser.add_argument(
        "--skip-upload",
        action="store_true",
        help="Download locally without uploading to Google Drive.",
    )
    return parser.parse_args()

def main() -> None:
    args = parse_args()
    repo_dir = Path(__file__).resolve().parent
    if args.skip_upload:
        result = backup_images(
            url=args.url,
            drive_folder_name=args.drive_folder_name,
            drive_parent_id=args.drive_parent_id,
            share_with_anyone=False,
            upload_to_drive=False,
            work_dir=Path(args.output_dir) if args.output_dir else repo_dir / "downloads",
            repo_dir=repo_dir,
        )
        print(f"Saved {result['image_count']} images to {result['local_output_dir']}")
        print(f"Manifest written to {result['manifest_path']}")
        print("Upload skipped.")
        return

    result = backup_images(
        url=args.url,
        drive_folder_name=args.drive_folder_name,
        drive_parent_id=args.drive_parent_id,
        share_with_anyone=True,
        upload_to_drive=True,
        work_dir=Path(args.output_dir) if args.output_dir else repo_dir / "downloads",
        repo_dir=repo_dir,
    )
    print(f"Saved {result['image_count']} images to {result['local_output_dir']}")
    print(f"Manifest written to {result['manifest_path']}")
    print(f"Drive folder: {result['drive_folder_link']}")


if __name__ == "__main__":
    main()
