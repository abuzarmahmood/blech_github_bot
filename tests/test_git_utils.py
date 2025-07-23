import unittest
from unittest.mock import patch, Mock
from src.git_utils import get_github_client, get_repository, get_open_issues


class TestGitUtils(unittest.TestCase):

    @patch('src.git_utils.Github')
    def test_get_github_client(self, MockGithub):
        mock_instance = MockGithub.return_value
        client = get_github_client()
        self.assertEqual(client, mock_instance)

    @patch('src.git_utils.Github')
    def test_get_repository(self, MockGithub):
        mock_instance = MockGithub.return_value
        mock_repo = Mock()
        mock_instance.get_repo.return_value = mock_repo
        repo = get_repository(mock_instance, 'owner/repo')
        self.assertEqual(repo, mock_repo)

    @patch('src.git_utils.Repository')
    def test_get_open_issues(self, MockRepository):
        mock_repo = MockRepository.return_value
        mock_issue = Mock()
        mock_repo.get_issues.return_value = [mock_issue]
        issues = get_open_issues(mock_repo)
        self.assertEqual(issues, [mock_issue])


if __name__ == '__main__':
    unittest.main()
