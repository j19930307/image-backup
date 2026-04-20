# tripleS Blog Image Drive Backup

This repo now supports two entry points:

- `backup_triples_blog_images.py`: CLI runner for local testing.
- `app.py`: Discord Slash Command webhook for Cloud Run.

## Discord Slash Command flow

1. Discord sends the slash command to `POST /interactions`.
2. Cloud Run verifies the Discord signature and immediately returns a deferred response.
3. A background worker downloads the article images, uploads them to Google Drive, and updates the original Discord response with the Drive folder link.

## Required environment variables

- `DISCORD_PUBLIC_KEY`: Discord application public key for signature validation.
- One Google Drive auth mode:
  - Personal Google Drive: `GOOGLE_OAUTH_TOKEN_JSON` or `GOOGLE_OAUTH_TOKEN_FILE`
  - Service account: `GOOGLE_SERVICE_ACCOUNT_JSON` or `GOOGLE_SERVICE_ACCOUNT_FILE`

## Optional environment variables

- `GOOGLE_DRIVE_PARENT_ID`: default parent folder ID in Google Drive.
- `GOOGLE_DRIVE_SHARE_WITH_ANYONE=true|false`: whether to make the folder link public. Default is `true`.
- `DISCORD_RESPONSE_EPHEMERAL=true|false`: whether the initial deferred response is ephemeral. Default is `true`.
- `WORKER_THREADS`: background worker thread count. Default is `4`.

## Slash command options

Recommended command name: `/backup_triples_images`

- `url`: target article URL.
- `folder_name`: target Google Drive folder name.
- `drive_parent_id`: optional Google Drive parent folder ID.

## Local CLI usage

```bash
python backup_triples_blog_images.py --url https://www.triplescosmos.com/blog/triples-msnz-taipei-concert-film-behind
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

5. For Cloud Run, put the contents of `token.json` into Secret Manager and expose it as `GOOGLE_OAUTH_TOKEN_JSON`.

The token is tied to your own Google account, so uploads go directly into your personal Drive instead of a service account Drive.

## Cloud Run deployment

```bash
gcloud run deploy triples-image-drive-backup --source . --region YOUR_REGION --allow-unauthenticated
```

After deployment, point the Discord interaction endpoint to:

```text
https://YOUR_CLOUD_RUN_URL/interactions
```

Recommended Cloud Run secrets for personal Drive:

- `DISCORD_PUBLIC_KEY`
- `GOOGLE_OAUTH_TOKEN_JSON`

If you want to keep uploads inside a specific folder, also set:

- `GOOGLE_DRIVE_PARENT_ID`

## GitHub auto deploy

This repo includes a GitHub Actions workflow at [.github/workflows/deploy-cloud-run.yml](./.github/workflows/deploy-cloud-run.yml).

When you push to `main`, GitHub Actions can redeploy the app to Cloud Run automatically.

One-time setup is documented in [DEPLOY.md](./DEPLOY.md). The workflow expects these GitHub repository secrets:

- `GCP_PROJECT_ID`
- `GCP_REGION`
- `CLOUD_RUN_SERVICE`
- `GCP_SERVICE_ACCOUNT`
- `GCP_WORKLOAD_IDENTITY_PROVIDER`

## Register Discord command

You can retry slash command registration with:

```powershell
.\scripts\register_discord_command.ps1
```

The script reads Discord values from `.env`.

There is also a Python version modeled after a typical `register_commands.py` workflow:

```powershell
python .\register_commands.py
```
