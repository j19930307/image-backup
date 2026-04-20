from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from flask import Flask, jsonify, request
from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

from backup_core import DEFAULT_DRIVE_FOLDER, DEFAULT_URL, backup_images

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
executor = ThreadPoolExecutor(max_workers=int(os.getenv("WORKER_THREADS", "4")))
REPO_DIR = Path(__file__).resolve().parent


def get_bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def verify_discord_request(raw_body: bytes) -> bool:
    public_key = os.getenv("DISCORD_PUBLIC_KEY")
    if not public_key:
        raise RuntimeError("DISCORD_PUBLIC_KEY is not configured.")

    signature = request.headers.get("X-Signature-Ed25519", "")
    timestamp = request.headers.get("X-Signature-Timestamp", "")
    verify_key = VerifyKey(bytes.fromhex(public_key))
    try:
        verify_key.verify(timestamp.encode("utf-8") + raw_body, bytes.fromhex(signature))
        return True
    except (BadSignatureError, ValueError):
        return False


def get_option(options: list[dict], name: str, default: str | None = None) -> str | None:
    for option in options:
        if option.get("name") == name:
            return option.get("value")
    return default


def format_success_message(result: dict[str, object], folder_name: str) -> str:
    return (
        "備份完成。\n"
        f"圖片數量: {result['image_count']}\n"
        f"Google Drive 資料夾: {folder_name}\n"
        f"資料夾連結: {result['drive_folder_link']}\n"
        f"來源網頁: {result['page_url']}"
    )


def update_interaction_response(application_id: str, interaction_token: str, content: str) -> None:
    response_url = f"https://discord.com/api/v10/webhooks/{application_id}/{interaction_token}/messages/@original"
    response = requests.patch(response_url, json={"content": content}, timeout=30)
    response.raise_for_status()


def process_backup(application_id: str, interaction_token: str, options: list[dict]) -> None:
    url = get_option(options, "url", DEFAULT_URL) or DEFAULT_URL
    folder_name = get_option(options, "folder_name", DEFAULT_DRIVE_FOLDER) or DEFAULT_DRIVE_FOLDER
    drive_parent_id = get_option(options, "drive_parent_id", os.getenv("GOOGLE_DRIVE_PARENT_ID"))
    share_with_anyone = get_bool_env("GOOGLE_DRIVE_SHARE_WITH_ANYONE", True)
    cleanup = None

    try:
        result = backup_images(
            url=url,
            drive_folder_name=folder_name,
            drive_parent_id=drive_parent_id,
            share_with_anyone=share_with_anyone,
            upload_to_drive=True,
            repo_dir=REPO_DIR,
        )
        cleanup = result.get("cleanup")
        content = format_success_message(result, folder_name)
        app.logger.info("Backup completed: %s", result["drive_folder_link"])
    except Exception as exc:  # noqa: BLE001
        app.logger.exception("Backup failed")
        content = f"備份失敗: {exc}"
    finally:
        if cleanup is not None:
            cleanup.cleanup()

    update_interaction_response(application_id, interaction_token, content)


@app.get("/")
def healthcheck():
    return jsonify({"ok": True})


@app.post("/interactions")
def interactions():
    raw_body = request.get_data()
    if not verify_discord_request(raw_body):
        return "invalid request signature", 401

    payload = request.get_json(force=True, silent=False)
    interaction_type = payload.get("type")

    if interaction_type == 1:
        return jsonify({"type": 1})

    if interaction_type != 2:
        return jsonify({"type": 4, "data": {"content": "Unsupported interaction type."}})

    data = payload.get("data", {})
    options = data.get("options", [])
    application_id = payload["application_id"]
    interaction_token = payload["token"]
    ephemeral = get_bool_env("DISCORD_RESPONSE_EPHEMERAL", True)

    executor.submit(process_backup, application_id, interaction_token, options)

    response_data: dict[str, int] = {}
    if ephemeral:
        response_data["flags"] = 64
    return jsonify({"type": 5, "data": response_data})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
