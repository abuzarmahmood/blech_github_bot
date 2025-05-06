import unittest
from src.git_utils import (
    clean_response,
    add_signature_to_comment,
    get_github_client,
    get_repository,
    get_open_issues,
    get_issue_comments,
    create_issue_comment,
    get_issue_details,
    search_issues,
    write_issue_response,
    clone_repository,
    update_repository,
    get_pr_branch,
    get_development_branch,
    create_pull_request,
    create_pull_request_from_issue,
    push_changes_with_authentication,
    is_pull_request,
    update_self_repo,
    perform_github_search,
    has_linked_pr,
    get_linked_pr
)
from github import Github
from unittest.mock import patch, MagicMock

class TestGitUtils(unittest.TestCase):

    @patch('src.git_utils.get_github_client')
    def test_get_github_client(self, mock_get_github_client):
        mock_get_github_client.return_value = MagicMock(spec=Github)
        client = get_github_client()
        self.assertIsInstance(client, Github)

    def test_clean_response(self):
        response = "This is a test response. "
        cleaned_response = clean_response(response)
        self.assertNotIn("", cleaned_response)

    def test_add_signature_to_comment(self):
        comment_text = "This is a comment."
        model = "test-model"
        signed_comment = add_signature_to_comment(comment_text, model)
        self.assertIn("test-model", signed_comment)

    # Add more tests for other functions...

if __name__ == '__main__':
    unittest.main()
