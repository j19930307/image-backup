from __future__ import annotations

from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/drive"]


def main() -> None:
    repo_dir = Path(__file__).resolve().parent
    credentials_path = repo_dir / "credentials.json"
    token_path = repo_dir / "token.json"

    if not credentials_path.exists():
        raise FileNotFoundError(
            f"Missing OAuth client file: {credentials_path}. Download a Desktop app OAuth client and save it as credentials.json."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
    creds = flow.run_local_server(port=0)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    print(f"Saved OAuth token to {token_path}")


if __name__ == "__main__":
    main()
