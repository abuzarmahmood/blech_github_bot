import unittest
from src.bot_tools import (
    get_local_repo_path,
    search_for_pattern,
    search_for_file,
    estimate_tokens,
    readfile,
    readlines
)


class TestBotTools(unittest.TestCase):

    def test_get_local_repo_path_exists(self):
        # Assuming a known repo path for testing
        repo_name = "known_owner/known_repo"
        expected_path = "/home/exouser/Desktop/blech_github_bot/src/repos/known_owner/known_repo"
        self.assertEqual(get_local_repo_path(repo_name), expected_path)

    def test_get_local_repo_path_not_exists(self):
        repo_name = "unknown_owner/unknown_repo"
        expected_message = "Repository unknown_owner/unknown_repo not found @ /home/exouser/Desktop/blech_github_bot/src/repos/unknown_owner/unknown_repo"
        self.assertEqual(get_local_repo_path(repo_name), expected_message)

    def test_search_for_pattern(self):
        search_dir = "/home/exouser/Desktop/blech_github_bot/src"
        pattern = "def "
        result = search_for_pattern(search_dir, pattern)
        self.assertIn("bot_tools.py", result)

    def test_search_for_file_exists(self):
        directory = "/home/exouser/Desktop/blech_github_bot/src"
        filename = "bot_tools.py"
        result = search_for_file(directory, filename)
        self.assertIn("bot_tools.py", result)

    def test_search_for_file_not_exists(self):
        directory = "/home/exouser/Desktop/blech_github_bot/src"
        filename = "non_existent_file.py"
        result = search_for_file(directory, filename)
        self.assertEqual(result, "File not found")

    def test_estimate_tokens(self):
        text = "This is a test sentence."
        self.assertEqual(estimate_tokens(text), 5)

        empty_text = ""
        self.assertEqual(estimate_tokens(empty_text), 0)

    def test_readfile(self):
        filepath = "/home/exouser/Desktop/blech_github_bot/src/bot_tools.py"
        content = readfile(filepath)
        self.assertIn("def get_local_repo_path", content)

    def test_readlines(self):
        filepath = "/home/exouser/Desktop/blech_github_bot/src/bot_tools.py"
        content = readlines(filepath, 0, 10)
        self.assertIn("def get_local_repo_path", content)


if __name__ == '__main__':
    unittest.main()
