from __future__ import annotations

import os

import requests
from dotenv import load_dotenv

load_dotenv()


def get_env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


APPLICATION_ID = get_env("DISCORD_APP_ID", "DISCORD_APPLICATION_ID", "APPLICATION_ID")
BOT_TOKEN = get_env("DISCORD_BOT_TOKEN", "BOT_TOKEN")
GUILD_ID = get_env("DISCORD_GUILD_ID")


def require_env(name: str, value: str | None) -> str:
    if value:
        return value
    raise RuntimeError(f"Missing required environment variable: {name}")


def build_backup_command() -> dict:
    return {
        "name": "backup_triples_images",
        "description": "Download blog images and back them up to Google Drive",
        "type": 1,
        "options": [
            {
                "name": "url",
                "description": "Target article URL",
                "type": 3,
                "required": False,
            },
            {
                "name": "folder_name",
                "description": "Google Drive folder name",
                "type": 3,
                "required": False,
            },
            {
                "name": "drive_parent_id",
                "description": "Optional Google Drive parent folder ID",
                "type": 3,
                "required": False,
            },
        ],
    }


def main() -> None:
    application_id = require_env("DISCORD_APP_ID", APPLICATION_ID)
    bot_token = require_env("DISCORD_BOT_TOKEN", BOT_TOKEN)

    if GUILD_ID:
        url = f"https://discord.com/api/v10/applications/{application_id}/guilds/{GUILD_ID}/commands"
        target = f"guild {GUILD_ID}"
    else:
        url = f"https://discord.com/api/v10/applications/{application_id}/commands"
        target = "global"

    response = requests.post(
        url,
        headers={
            "Authorization": f"Bot {bot_token}",
            "Content-Type": "application/json",
        },
        json=build_backup_command(),
        timeout=30,
    )
    response.raise_for_status()

    body = response.json()
    print(f"Registered /backup_triples_images command to {target}: {body['id']}")


if __name__ == "__main__":
    main()
