import unittest

from sync_blog_posts_to_notion import build_page_properties, find_existing_page_id


class FindExistingPageIdTests(unittest.TestCase):
    def test_prefers_new_url_when_matching_an_existing_page(self) -> None:
        # Arrange
        post = {
            "url": "https://www.triplescosmos.com/blog/legacy-post",
            "new_url": "https://www.triplescosmos.com/channels/current-post",
        }
        pages_by_url = {
            "https://www.triplescosmos.com/blog/legacy-post": "legacy-page",
            "https://www.triplescosmos.com/channels/current-post": "current-page",
        }

        # Act
        page_id = find_existing_page_id(post, pages_by_url)

        # Assert
        self.assertEqual("current-page", page_id)

    def test_uses_old_url_when_the_new_site_has_no_matching_url(self) -> None:
        # Arrange
        post = {"url": "https://www.triplescosmos.com/blog/legacy-only-post"}
        pages_by_url = {"https://www.triplescosmos.com/blog/legacy-only-post": "legacy-page"}

        # Act
        page_id = find_existing_page_id(post, pages_by_url)

        # Assert
        self.assertEqual("legacy-page", page_id)

    def test_keeps_new_url_empty_for_a_legacy_only_post(self) -> None:
        # Arrange
        post = {"url": "https://www.triplescosmos.com/blog/legacy-only-post"}

        # Act
        properties = build_page_properties(post)

        # Assert
        self.assertIsNone(properties["New URL"]["url"])


if __name__ == "__main__":
    unittest.main()
