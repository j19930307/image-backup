from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

import discord
from discord import app_commands
from dotenv import load_dotenv

from backup_core import DEFAULT_DRIVE_FOLDER, DEFAULT_URL, backup_images

load_dotenv()

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)
REPO_DIR = Path(__file__).resolve().parent


def get_env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def get_bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def require_env(name: str, value: str | None) -> str:
    if value:
        return value
    raise RuntimeError(f"Missing required environment variable: {name}")


def format_success_message(result: dict[str, object], folder_name: str) -> str:
    return (
        "備份完成。\n"
        f"圖片數量: {result['image_count']}\n"
        f"Google Drive 資料夾: {folder_name}\n"
        f"資料夾連結: {result['drive_folder_link']}\n"
        f"來源網頁: {result['page_url']}"
    )


def run_backup(
    url: str,
    folder_name: str,
    drive_parent_id: str | None,
    share_with_anyone: bool,
) -> str:
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
        LOGGER.info("Backup completed: %s", result["drive_folder_link"])
        return format_success_message(result, folder_name)
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("Backup failed")
        return f"備份失敗: {exc}"
    finally:
        if cleanup is not None:
            cleanup.cleanup()


intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)


@bot.event
async def on_ready() -> None:
    guild_id = get_env("DISCORD_GUILD_ID")
    if guild_id:
        guild = discord.Object(id=int(guild_id))
        tree.copy_global_to(guild=guild)
        synced = await tree.sync(guild=guild)
        LOGGER.info("Synced %s command(s) to guild %s", len(synced), guild_id)
    else:
        synced = await tree.sync()
        LOGGER.info("Synced %s global command(s)", len(synced))

    LOGGER.info("Logged in as %s (%s)", bot.user, bot.user.id if bot.user else "unknown")


@tree.command(name="backup_triples_images", description="Download blog images and back them up to Google Drive")
@app_commands.describe(
    url="Target article URL",
    folder_name="Google Drive folder name",
    drive_parent_id="Optional Google Drive parent folder ID",
)
async def backup_triples_images(
    interaction: discord.Interaction,
    url: str = DEFAULT_URL,
    folder_name: str = DEFAULT_DRIVE_FOLDER,
    drive_parent_id: str | None = None,
) -> None:
    ephemeral = get_bool_env("DISCORD_RESPONSE_EPHEMERAL", True)
    await interaction.response.defer(ephemeral=ephemeral, thinking=True)

    resolved_parent_id = drive_parent_id or get_env("GOOGLE_DRIVE_PARENT_ID")
    share_with_anyone = get_bool_env("GOOGLE_DRIVE_SHARE_WITH_ANYONE", True)
    content = await asyncio.to_thread(
        run_backup,
        url,
        folder_name,
        resolved_parent_id,
        share_with_anyone,
    )
    await interaction.edit_original_response(content=content)


def main() -> None:
    token = require_env("DISCORD_BOT_TOKEN", get_env("DISCORD_BOT_TOKEN", "BOT_TOKEN"))
    bot.run(token)


if __name__ == "__main__":
    main()
