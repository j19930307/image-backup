# tripleS Blog Image Drive Backup

This repo now supports local execution first:

- `discord_bot.py`: local Discord bot with slash command support.
- `backup_triples_blog_images.py`: CLI runner for local testing.

## Local Discord bot flow

1. Run `discord_bot.py` on your own computer.
2. The bot logs in through the Discord gateway.
3. `/backup_triples_images` defers the reply, downloads the article images, uploads them to Google Drive, then sends the folder link back in Discord.

## Required environment variables

- `DISCORD_BOT_TOKEN`: bot token for the local Discord bot.
- One Google Drive auth mode:
  - Personal Google Drive: `GOOGLE_OAUTH_TOKEN_JSON` or `GOOGLE_OAUTH_TOKEN_FILE`
  - Service account: `GOOGLE_SERVICE_ACCOUNT_JSON` or `GOOGLE_SERVICE_ACCOUNT_FILE`

## Optional environment variables

- `DISCORD_GUILD_ID`: guild ID for faster command sync during local testing.
- `GOOGLE_DRIVE_PARENT_ID`: default parent folder ID in Google Drive.
- `GOOGLE_DRIVE_SHARE_WITH_ANYONE=true|false`: whether to make the folder link public. Default is `true`.
- `DISCORD_RESPONSE_EPHEMERAL=true|false`: whether the bot response is ephemeral. Default is `true`.

## Slash command options

Command name: `/backup_triples_images`

- `url`: target article URL.
- `folder_name`: target Google Drive folder name.
- `drive_parent_id`: optional Google Drive parent folder ID.

## Local Discord bot usage

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Run the bot:

```bash
python discord_bot.py
```

If `.env` already contains `DISCORD_BOT_TOKEN` and `DISCORD_GUILD_ID`, the bot will sync the slash command automatically on startup.

## Local CLI usage

```bash
python backup_triples_blog_images.py --url https://www.triplescosmos.com/blog/triples-msnz-taipei-concert-film-behind
```

You can also scrape all blog post titles and links:

```bash
python scrape_blog_posts.py
```

You can then back up every article's images to Google Drive and write the Drive folder info back into `blog_posts.json`:

```bash
python backup_blog_posts_to_drive.py
```

To refresh the list later and back up only new posts:

```bash
python sync_new_blog_posts.py
```

## Personal Google Drive OAuth setup

Use this if your Drive is a personal Google account.

1. In Google Cloud Console, enable the Google Drive API.
2. Create an OAuth client of type `Desktop app`.
3. Download the OAuth client JSON and save it as `credentials.json` in this repo.
4. Generate `token.json` locally:

```bash
python generate_oauth_token.py
```

The token is tied to your own Google account, so uploads go directly into your personal Drive instead of a service account Drive.

## Register Discord command

Explicit command registration is not required because `discord_bot.py` syncs commands on startup.
