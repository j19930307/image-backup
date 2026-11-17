import importlib
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


def _install_stub_modules_if_missing() -> None:
    """Allow importing backup_core in minimal environments without runtime deps."""

    def ensure_module(name: str) -> tuple[types.ModuleType, bool]:
        if name in sys.modules:
            return sys.modules[name], False
        try:
            return importlib.import_module(name), False
        except ImportError:
            mod = types.ModuleType(name)
            sys.modules[name] = mod
            return mod, True

    httplib2_mod, created = ensure_module("httplib2")
    if created:
        httplib2_mod.Http = MagicMock()
    ensure_module("requests")
    bs4_mod, created = ensure_module("bs4")
    if created:
        bs4_mod.BeautifulSoup = MagicMock()

    google, google_created = ensure_module("google")
    google_auth, auth_created = ensure_module("google.auth")
    if google_created and auth_created:
        google.auth = google_auth
    ensure_module("google.oauth2")
    sa_mod, created = ensure_module("google.oauth2.service_account")
    if created:
        sa_mod.Credentials = MagicMock()
    creds_mod, created = ensure_module("google.oauth2.credentials")
    if created:
        creds_mod.Credentials = MagicMock()
    auth_http_mod, created = ensure_module("google_auth_httplib2")
    if created:
        auth_http_mod.AuthorizedHttp = MagicMock()
    flow_mod, created = ensure_module("google_auth_oauthlib.flow")
    if created:
        flow_mod.InstalledAppFlow = MagicMock()

    ensure_module("googleapiclient")
    disc_mod, created = ensure_module("googleapiclient.discovery")
    if created:
        disc_mod.build = MagicMock()
    http_mod, created = ensure_module("googleapiclient.http")
    if created:
        http_mod.MediaFileUpload = MagicMock()


_install_stub_modules_if_missing()

import backup_core  # noqa: E402


class BackupCoreDriveTests(unittest.TestCase):
    def test_list_drive_folder_files_handles_pagination(self) -> None:
        service = MagicMock()
        list_call = service.files.return_value.list
        list_call.return_value.execute.side_effect = [
            {
                "files": [{"id": "1", "name": "a.jpg", "webViewLink": "https://drive/1"}],
                "nextPageToken": "page-2",
            },
            {
                "files": [{"id": "2", "name": "b.jpg", "webViewLink": "https://drive/2"}],
            },
        ]

        result = backup_core.list_drive_folder_files(service, "folder-123")

        self.assertEqual({"a.jpg", "b.jpg"}, set(result.keys()))
        self.assertEqual(2, list_call.return_value.execute.call_count)
        list_call.return_value.execute.assert_called_with(num_retries=backup_core.DEFAULT_DRIVE_RETRIES)

    def test_backup_images_skips_existing_drive_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            output_dir = work_dir / "sample-post"
            output_dir.mkdir(parents=True)
            (output_dir / "01.jpg").write_bytes(b"x" * 200)
            (output_dir / "02.jpg").write_bytes(b"y" * 200)

            service = MagicMock()
            manifest = [
                {"index": "1", "url": "https://img/01.jpg", "file_name": "01.jpg", "content_type": "image/jpeg", "size_bytes": "200"},
                {"index": "2", "url": "https://img/02.jpg", "file_name": "02.jpg", "content_type": "image/jpeg", "size_bytes": "200"},
            ]

            with (
                patch.object(backup_core, "download_images", return_value=manifest),
                patch.object(backup_core, "build_drive_service", return_value=service),
                patch.object(backup_core, "ensure_drive_folder", return_value="folder-123"),
                patch.object(
                    backup_core,
                    "list_drive_folder_files",
                    return_value={"01.jpg": {"id": "f1", "name": "01.jpg"}},
                ),
                patch.object(backup_core, "upload_file") as mock_upload,
                patch.object(backup_core, "get_folder_link", return_value="https://drive.google.com/drive/folders/folder-123"),
            ):
                result = backup_core.backup_images(
                    url="https://www.triplescosmos.com/blog/sample-post",
                    drive_folder_name="Sample Post",
                    upload_to_drive=True,
                    upload_manifest=False,
                    work_dir=work_dir,
                    image_urls=["https://img/01.jpg", "https://img/02.jpg"],
                )

            self.assertEqual(2, result["image_count"])
            self.assertEqual("https://drive.google.com/drive/folders/folder-123", result["drive_folder_link"])
            mock_upload.assert_called_once()
            uploaded_path = mock_upload.call_args.args[1]
            self.assertEqual("02.jpg", uploaded_path.name)

    def test_upload_file_uses_resumable_and_retries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "photo.jpg"
            file_path.write_bytes(b"data")
            service = MagicMock()
            service.files.return_value.create.return_value.execute.return_value = {
                "id": "file-1",
                "webViewLink": "https://drive.google.com/file/d/file-1/view",
            }

            with patch.object(backup_core, "MediaFileUpload") as mock_media:
                link = backup_core.upload_file(service, file_path, "folder-123")

            self.assertEqual("https://drive.google.com/file/d/file-1/view", link)
            mock_media.assert_called_once_with(str(file_path), mimetype="image/jpeg", resumable=True)
            service.files.return_value.create.return_value.execute.assert_called_once_with(
                num_retries=backup_core.DEFAULT_DRIVE_RETRIES
            )


if __name__ == "__main__":
    unittest.main()
