import unittest

from sync_new_blog_posts import merge_posts


class MergePostsTests(unittest.TestCase):
    def test_preserves_legacy_backups_and_adds_only_unseen_current_posts(self) -> None:
        # Arrange
        existing = [
            {
                "title": "[tripleS] <ASSEMLE26> behind",
                "url": "https://www.triplescosmos.com/blog/legacy-match",
                "drive_folder_link": "https://drive.google.com/legacy-match",
            },
            {
                "title": "[tripleS] legacy post no longer listed",
                "url": "https://www.triplescosmos.com/blog/legacy-missing",
                "drive_folder_link": "https://drive.google.com/legacy-missing",
            },
        ]
        current = [
            {
                "title": "[tripleS] <ASSEMBLE26> behind",
                "url": "https://www.triplescosmos.com/channels/current-match",
                "image_urls": ["https://images.example/match.jpg"],
            },
            {
                "title": "[tripleS] new-only post",
                "url": "https://www.triplescosmos.com/channels/new-only",
                "image_urls": ["https://images.example/new.jpg"],
            },
        ]

        # Act
        merged, new_count = merge_posts(existing, current)

        # Assert
        self.assertEqual(3, len(merged))
        self.assertEqual(1, new_count)
        self.assertEqual("https://drive.google.com/legacy-missing", merged[1]["drive_folder_link"])
        self.assertEqual("https://www.triplescosmos.com/channels/current-match", merged[0]["new_url"])


if __name__ == "__main__":
    unittest.main()
