from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import mimetypes
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote, urljoin, urlparse

import google.auth
import requests
from bs4 import BeautifulSoup
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials as UserCredentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/drive"]
DEFAULT_URL = "https://www.triplescosmos.com/blog/triples-msnz-taipei-concert-film-behind"
DEFAULT_DRIVE_FOLDER = "tripleS Taipei Concert Film Backup"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
)
SOCIAL_KEYWORDS = ("icon", "logo", "discord", "instagram", "youtube", "tiktok", "facebook", "twitter")
DEFAULT_MIN_IMAGE_BYTES = 100 * 1024
DEFAULT_DOWNLOAD_WORKERS = 8


def slug_from_url(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    slug = Path(path).name or "triples-blog-images"
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", slug).strip("-")


def sanitize_drive_folder_name(name: str, fallback: str | None = None) -> str:
    sanitized = re.sub(r'[<>:"/\\|?*]+', " ", name)
    sanitized = re.sub(r"\s+", " ", sanitized).strip().rstrip(".")
    if sanitized:
        return sanitized[:200]
    if fallback:
        return sanitize_drive_folder_name(fallback)
    return "triples-blog-images"


def fetch_html(url: str) -> str:
    response = requests.get(url, timeout=30, headers={"User-Agent": USER_AGENT})
    response.raise_for_status()
    return response.text


def extract_image_urls(base_url: str, html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[str] = []

    for img in soup.select("img"):
        if img.find_parent(["header", "footer", "nav"]):
            continue
        src = img.get("src")
        if src:
            candidates.append(urljoin(base_url, src))

    deduped: list[str] = []
    seen: set[str] = set()
    for url in candidates:
        parsed = urlparse(url)
        if not parsed.scheme.startswith("http"):
            continue
        path = parsed.path.lower()
        if not any(path.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif")):
            continue
        if any(keyword in path for keyword in SOCIAL_KEYWORDS):
            continue
        if url in seen:
            continue
        seen.add(url)
        deduped.append(url)

    if not deduped:
        raise RuntimeError("No downloadable image URLs found on the page.")
    return deduped


def guess_extension_from_content_type(content_type: str, url: str) -> str:
    content_type = content_type.split(";")[0].strip().lower()
    guessed = mimetypes.guess_extension(content_type) if content_type else None
    if guessed == ".jpe":
        guessed = ".jpg"
    if guessed:
        return guessed
    suffix = Path(urlparse(url).path).suffix
    return suffix or ".bin"


def build_output_name(image_url: str, used_names: set[str]) -> str:
    parsed_path = Path(urlparse(image_url).path)
    original_name = sanitize_file_name(unquote(parsed_path.name or "downloaded-file"))
    stem = Path(original_name).stem or "downloaded-file"
    suffix = Path(original_name).suffix

    candidate = original_name
    counter = 1
    while candidate in used_names:
        candidate = f"{stem}_{counter}{suffix}"
        counter += 1

    used_names.add(candidate)
    return candidate


def sanitize_file_name(file_name: str, max_stem_length: int = 120) -> str:
    path = Path(file_name)
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", path.stem).strip(" ._")
    suffix = re.sub(r"[^a-zA-Z0-9.]+", "", path.suffix)
    if not stem:
        stem = "downloaded-file"
    return f"{stem[:max_stem_length]}{suffix[:16]}"


def fetch_image_bytes(image_url: str) -> tuple[str, bytes, str]:
    response = requests.get(image_url, timeout=60, headers={"User-Agent": USER_AGENT})
    response.raise_for_status()
    return image_url, response.content, response.headers.get("Content-Type", "")


def download_images(
    image_urls: Iterable[str],
    output_dir: Path,
    min_image_bytes: int = DEFAULT_MIN_IMAGE_BYTES,
    max_workers: int = DEFAULT_DOWNLOAD_WORKERS,
) -> list[dict[str, str]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, str]] = []
    used_names: set[str] = set()
    downloaded_items: list[tuple[str, bytes, str]] = []

    with ThreadPoolExecutor(max_workers=max(1, max_workers)) as executor:
        for image_url, content, content_type in executor.map(fetch_image_bytes, image_urls):
            if len(content) < min_image_bytes:
                continue
            downloaded_items.append((image_url, content, content_type))

    for index, (image_url, content, content_type) in enumerate(downloaded_items, start=1):
        file_name = build_output_name(image_url, used_names)
        if not Path(file_name).suffix:
            file_name = f"{Path(file_name).stem}{guess_extension_from_content_type(content_type, image_url)}"
        file_path = output_dir / file_name
        file_path.write_bytes(content)
        manifest.append(
            {
                "index": str(index),
                "url": image_url,
                "file_name": file_name,
                "content_type": content_type,
                "size_bytes": str(file_path.stat().st_size),
            }
        )

    if not manifest:
        raise RuntimeError("No downloadable article images remained after filtering small assets.")

    return manifest


def write_manifest(output_dir: Path, page_url: str, image_manifest: list[dict[str, str]]) -> Path:
    manifest_path = output_dir / "manifest.json"
    payload = {
        "page_url": page_url,
        "downloaded_at": datetime.now().isoformat(timespec="seconds"),
        "image_count": len(image_manifest),
        "images": image_manifest,
    }
    manifest_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest_path


def load_drive_credentials(repo_dir: Path | None = None):
    oauth_token_json = os.getenv("GOOGLE_OAUTH_TOKEN_JSON")
    if oauth_token_json:
        return UserCredentials.from_authorized_user_info(json.loads(oauth_token_json), SCOPES)

    oauth_token_file = os.getenv("GOOGLE_OAUTH_TOKEN_FILE")
    if oauth_token_file:
        return UserCredentials.from_authorized_user_file(oauth_token_file, SCOPES)

    service_account_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if service_account_json:
        info = json.loads(service_account_json)
        return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)

    service_account_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
    if service_account_file:
        return service_account.Credentials.from_service_account_file(service_account_file, scopes=SCOPES)

    if repo_dir is not None:
        token_path = repo_dir / "token.json"
        credentials_path = repo_dir / "credentials.json"
        creds = None
        if token_path.exists():
            creds = UserCredentials.from_authorized_user_file(token_path, SCOPES)
        if creds and creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request

            creds.refresh(Request())
            token_path.write_text(creds.to_json(), encoding="utf-8")
            return creds
        if creds and creds.valid:
            return creds
        oauth_client_json = os.getenv("GOOGLE_OAUTH_CLIENT_JSON")
        if oauth_client_json:
            oauth_client_path = repo_dir / ".oauth_client.json"
            oauth_client_path.write_text(oauth_client_json, encoding="utf-8")
            flow = InstalledAppFlow.from_client_secrets_file(str(oauth_client_path), SCOPES)
            creds = flow.run_local_server(port=0)
            token_path.write_text(creds.to_json(), encoding="utf-8")
            return creds
        if credentials_path.exists():
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
            creds = flow.run_local_server(port=0)
            token_path.write_text(creds.to_json(), encoding="utf-8")
            return creds

    creds, _ = google.auth.default(scopes=SCOPES)
    return creds


def build_drive_service(repo_dir: Path | None = None):
    creds = load_drive_credentials(repo_dir)
    return build("drive", "v3", credentials=creds)


def ensure_drive_folder(service, folder_name: str, parent_id: str | None) -> str:
    escaped_name = folder_name.replace("'", "\\'")
    query_parts = [
        "mimeType = 'application/vnd.google-apps.folder'",
        f"name = '{escaped_name}'",
        "trashed = false",
    ]
    if parent_id:
        query_parts.append(f"'{parent_id}' in parents")

    response = (
        service.files()
        .list(q=" and ".join(query_parts), spaces="drive", fields="files(id, name, webViewLink)")
        .execute()
    )
    files = response.get("files", [])
    if files:
        return files[0]["id"]

    metadata = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if parent_id:
        metadata["parents"] = [parent_id]

    created = service.files().create(body=metadata, fields="id").execute()
    return created["id"]


def ensure_public_permission(service, file_id: str) -> None:
    permissions = (
        service.permissions()
        .list(fileId=file_id, fields="permissions(id, type, role)")
        .execute()
        .get("permissions", [])
    )
    if any(item.get("type") == "anyone" and item.get("role") == "reader" for item in permissions):
        return

    service.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "reader"},
        fields="id",
    ).execute()


def upload_file(service, file_path: Path, folder_id: str) -> str:
    mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    metadata = {"name": file_path.name, "parents": [folder_id]}
    media = MediaFileUpload(str(file_path), mimetype=mime_type, resumable=False)
    uploaded = service.files().create(body=metadata, media_body=media, fields="id, webViewLink").execute()
    return uploaded.get("webViewLink", "")


def get_folder_link(service, folder_id: str, share_with_anyone: bool = True) -> str:
    if share_with_anyone:
        ensure_public_permission(service, folder_id)
    metadata = service.files().get(fileId=folder_id, fields="webViewLink").execute()
    return metadata.get("webViewLink") or f"https://drive.google.com/drive/folders/{folder_id}"


def backup_images(
    url: str = DEFAULT_URL,
    drive_folder_name: str = DEFAULT_DRIVE_FOLDER,
    drive_parent_id: str | None = None,
    share_with_anyone: bool = True,
    upload_to_drive: bool = True,
    upload_manifest: bool = True,
    min_image_bytes: int = DEFAULT_MIN_IMAGE_BYTES,
    max_download_workers: int = DEFAULT_DOWNLOAD_WORKERS,
    work_dir: Path | None = None,
    repo_dir: Path | None = None,
) -> dict[str, object]:
    slug = slug_from_url(url)
    if work_dir is None:
        temp_dir = tempfile.TemporaryDirectory(prefix="triples-image-backup-")
        base_dir = Path(temp_dir.name)
    else:
        temp_dir = None
        base_dir = work_dir

    output_dir = base_dir / slug
    html = fetch_html(url)
    image_urls = extract_image_urls(url, html)
    manifest = download_images(
        image_urls,
        output_dir,
        min_image_bytes=min_image_bytes,
        max_workers=max_download_workers,
    )
    manifest_path = write_manifest(output_dir, url, manifest)

    result = {
        "page_url": url,
        "image_count": len(manifest),
        "local_output_dir": str(output_dir),
        "manifest_path": str(manifest_path),
        "downloaded_files": [item["file_name"] for item in manifest],
    }

    if upload_to_drive:
        service = build_drive_service(repo_dir)
        safe_drive_folder_name = sanitize_drive_folder_name(drive_folder_name, slug)
        folder_id = ensure_drive_folder(service, safe_drive_folder_name, drive_parent_id)

        for file_path in sorted(output_dir.iterdir()):
            if file_path.is_file():
                if not upload_manifest and file_path.name == "manifest.json":
                    continue
                upload_file(service, file_path, folder_id)

        folder_link = get_folder_link(service, folder_id, share_with_anyone=share_with_anyone)
        result["drive_folder_id"] = folder_id
        result["drive_folder_link"] = folder_link
        result["drive_folder_name"] = safe_drive_folder_name

    if temp_dir is not None:
        result["cleanup"] = temp_dir
    return result
