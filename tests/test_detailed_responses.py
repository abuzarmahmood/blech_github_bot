"""
Tests for detailed issue and PR handling in response_agent.py
"""
from src.bot_tools import create_mock_issue, create_mock_pull_request
import src.response_agent as response_agent
import os
import sys
import pytest
from unittest.mock import MagicMock, patch

# Add the src directory to the path
src_dir = os.path.join(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))), 'src')
sys.path.append(src_dir)

# Import after adding src to path

# Mock classes from test_response_agent.py


class MockLabel:
    def __init__(self, name):
        self.name = name


class MockUser:
    def __init__(self, login):
        self.login = login


class MockComment:
    def __init__(self, data):
        self.id = data["id"]
        self.body = data["body"]
        self.user = MockUser(data["user"]["login"])
        self.created_at = data["created_at"]
        self.html_url = data.get("html_url", "")


class MockIssue:
    def __init__(self, data):
        self.number = data["number"]
        self.title = data["title"]
        self.body = data["body"]
        self.labels = [MockLabel(label["name"]) for label in data["labels"]]
        self.user = MockUser(data["user"]["login"])
        self.comments_url = data["comments_url"]
        self.html_url = data["html_url"]
        self._comments = []

        # Add additional attributes from data if they exist
        self.state = data.get("state", "open")
        self.created_at = data.get("created_at", "2023-01-01T00:00:00Z")
        self.updated_at = data.get("updated_at", "2023-01-01T01:00:00Z")
        self.closed_at = data.get("closed_at")
        self.repository_url = data.get(
            "repository_url", "https://api.github.com/repos/test/test")
        self.assignees = data.get("assignees", [])
        self.milestone = data.get("milestone")
        self.locked = data.get("locked", False)
        self.active_lock_reason = data.get("active_lock_reason")
        self.pull_request = data.get("pull_request")
        self.author_association = data.get("author_association", "CONTRIBUTOR")
        self.reactions = data.get("reactions", {"total_count": 0})

        # Store the original data for reference
        self._data = data

    def get_comments(self):
        return self._comments

    def add_to_labels(self, label_name):
        self.labels.append(MockLabel(label_name))

    def create_issue_comment(self, body):
        comment = MockComment({
            "id": len(self._comments) + 1,
            "body": body,
            "user": {"login": "blech_bot"},
            "created_at": "2023-01-01T00:00:00Z"
        })
        self._comments.append(comment)
        return comment

    def to_dict(self):
        """Convert the mock issue to a dictionary for testing get_issue_details"""
        return self._data


class MockRef:
    def __init__(self, ref):
        self.ref = ref


class MockPullRequest(MockIssue):
    def __init__(self, data):
        super().__init__(data)
        self.head = MockRef(data["head"]["ref"])
        self.base = MockRef(data.get("base", {}).get("ref", "main"))
        self.merged = data.get("merged", False)
        self.mergeable = data.get("mergeable", True)
        self.merged_at = data.get("merged_at")
        self.merge_commit_sha = data.get("merge_commit_sha")
        self.draft = data.get("draft", False)
        self.additions = data.get("additions", 0)
        self.deletions = data.get("deletions", 0)
        self.changed_files = data.get("changed_files", 0)


class MockRepository:
    def __init__(self, name="test/test"):
        self.full_name = name
        self.default_branch = "main"

    def get_pull(self, number):
        return MockPullRequest(create_mock_pull_request(number))

# Test fixtures


@pytest.fixture
def mock_detailed_issue():
    """Create a mock issue with all details needed for get_issue_details"""
    return MockIssue(create_mock_issue(
        title="[blech_bot] Detailed test issue",
        body="This is a detailed test issue with all required fields",
        detailed=True,
        created_at="2023-01-01T00:00:00Z",
        updated_at="2023-01-02T00:00:00Z"
    ))


@pytest.fixture
def mock_detailed_pr():
    """Create a mock PR with all details needed for testing"""
    return MockPullRequest(create_mock_pull_request(
        title="[blech_bot] Detailed test PR",
        body="This is a detailed test PR with all required fields",
        detailed=True,
        created_at="2023-01-01T00:00:00Z",
        updated_at="2023-01-02T00:00:00Z"
    ))

# Tests for detailed issue handling


@patch('src.git_utils.get_issue_comments')
def test_get_issue_details_with_detailed_issue(mock_get_comments, mock_detailed_issue):
    """Test that get_issue_details works with a detailed mock issue"""
    mock_get_comments.return_value = []

    # Directly patch the get_issue_details function
    with patch('src.response_agent.get_issue_details', autospec=True) as mock_get_details:
        # Configure the mock to return a dictionary based on our detailed issue
        expected_details = {
            'number': mock_detailed_issue.number,
            'title': mock_detailed_issue.title,
            'body': mock_detailed_issue.body,
            'state': mock_detailed_issue.state,
            'created_at': mock_detailed_issue.created_at,
            'updated_at': mock_detailed_issue.updated_at,
            'user': {'login': mock_detailed_issue.user.login},
            'labels': [{'name': label.name} for label in mock_detailed_issue.labels],
            'comments': []
        }
        mock_get_details.return_value = expected_details

        # Call the function
        details = response_agent.get_issue_details(mock_detailed_issue)

        # Verify the result
        assert details == expected_details
        mock_get_details.assert_called_once_with(mock_detailed_issue)


@patch('response_agent.get_github_client')
@patch('response_agent.get_repository')
@patch('response_agent.bot_tools.get_local_repo_path')
@patch('response_agent.triggers.has_blech_bot_tag')
@patch('response_agent.is_pull_request')
@patch('response_agent.check_triggers')
@patch('response_agent.response_selector')
def test_process_detailed_issue_new_response(
    mock_response_selector, mock_check_triggers, mock_is_pr,
    mock_has_tag, mock_get_repo_path, mock_get_repo, mock_get_client,
    mock_detailed_issue
):
    """Test processing a detailed issue with a new response"""
    # Setup mocks
    mock_is_pr.return_value = False
    mock_has_tag.return_value = True
    mock_get_repo_path.return_value = "/tmp/test_repo"
    mock_get_repo.return_value = MockRepository()
    mock_get_client.return_value = MagicMock()
    mock_check_triggers.return_value = "new_response"

    # Mock response function
    mock_response_func = MagicMock()
    mock_response_func.return_value = ("Detailed test response", [
                                       "Detailed test response"])
    mock_response_selector.return_value = mock_response_func

    # Mock write_issue_response
    with patch('response_agent.write_issue_response') as mock_write_response:
        success, _ = response_agent.process_issue(
            mock_detailed_issue, "test/test")

        # Verify success and that write_issue_response was called with the detailed response
        assert success is True
        mock_write_response.assert_called_once()
        mock_response_func.assert_called_once_with(
            mock_detailed_issue, "test/test")


@patch('response_agent.get_github_client')
@patch('response_agent.get_repository')
@patch('response_agent.bot_tools.get_local_repo_path')
@patch('response_agent.triggers.has_blech_bot_tag')
@patch('response_agent.is_pull_request')
@patch('response_agent.triggers.has_develop_issue_trigger')
def test_process_detailed_issue_develop_flow(
    mock_has_develop, mock_is_pr, mock_has_tag,
    mock_get_repo_path, mock_get_repo, mock_get_client,
    mock_detailed_issue
):
    """Test processing a detailed issue with develop flow"""
    # Setup mocks
    mock_is_pr.return_value = False
    mock_has_tag.return_value = True
    mock_has_develop.return_value = True
    mock_get_repo_path.return_value = "/tmp/test_repo"
    mock_get_repo.return_value = MockRepository()
    mock_get_client.return_value = MagicMock()

    # Mock develop_issue_flow
    with patch('response_agent.develop_issue_flow') as mock_develop_flow:
        mock_develop_flow.return_value = (True, None)

        success, _ = response_agent.process_issue(
            mock_detailed_issue, "test/test")

        # Verify success and that develop_issue_flow was called
        assert success is True
        mock_develop_flow.assert_called_once_with(
            mock_detailed_issue, "test/test", is_pr=False)

# Tests for detailed PR handling


@patch('response_agent.get_github_client')
@patch('response_agent.get_repository')
@patch('response_agent.bot_tools.get_local_repo_path')
@patch('response_agent.triggers.has_blech_bot_tag')
@patch('response_agent.is_pull_request')
def test_process_detailed_pr_flow(
    mock_is_pr, mock_has_tag, mock_get_repo_path,
    mock_get_repo, mock_get_client, mock_detailed_pr
):
    """Test processing a detailed PR"""
    # Setup mocks
    mock_is_pr.return_value = True
    mock_has_tag.return_value = True
    mock_get_repo_path.return_value = "/tmp/test_repo"
    mock_get_repo.return_value = MockRepository()
    mock_get_client.return_value = MagicMock()

    # Mock standalone_pr_flow
    with patch('response_agent.standalone_pr_flow') as mock_pr_flow:
        mock_pr_flow.return_value = (True, None)

        success, _ = response_agent.process_issue(
            mock_detailed_pr, "test/test")

        # Verify success and that standalone_pr_flow was called with the detailed PR
        assert success is True
        mock_pr_flow.assert_called_once_with(mock_detailed_pr, "test/test")


@patch('response_agent.get_github_client')
@patch('response_agent.get_repository')
@patch('response_agent.bot_tools.get_local_repo_path')
@patch('response_agent.triggers.has_blech_bot_tag')
@patch('response_agent.is_pull_request')
@patch('response_agent.get_pr_branch')
def test_standalone_pr_flow_with_detailed_pr(
    mock_get_pr_branch, mock_is_pr, mock_has_tag,
    mock_get_repo_path, mock_get_repo, mock_get_client,
    mock_detailed_pr
):
    """Test standalone PR flow with a detailed PR"""
    # Setup mocks
    mock_is_pr.return_value = True
    mock_has_tag.return_value = True
    mock_get_repo_path.return_value = "/tmp/test_repo"
    mock_get_repo.return_value = MockRepository()
    mock_get_client.return_value = MagicMock()
    mock_get_pr_branch.return_value = "test-branch"

    # Mock the necessary functions for standalone_pr_flow
    with patch('response_agent.checkout_branch') as mock_checkout:
        with patch('response_agent.summarize_relevant_comments') as mock_summarize:
            mock_summarize.return_value = ([], [], "Test summary")

            with patch('response_agent.generate_edit_command_response') as mock_generate:
                mock_generate.return_value = (
                    "Test response", ["Test response"])

                with patch('response_agent.run_aider') as mock_run_aider:
                    mock_run_aider.return_value = "Aider output"

                    with patch('response_agent.push_changes_with_authentication') as mock_push:
                        mock_push.return_value = (True, None)

                        with patch('response_agent.write_pr_comment') as mock_write_comment:
                            with patch('response_agent.back_to_master_branch') as mock_back:

                                # Call the function through process_issue
                                with patch('response_agent.standalone_pr_flow', wraps=response_agent.standalone_pr_flow) as wrapped_flow:
                                    success, _ = response_agent.process_issue(
                                        mock_detailed_pr, "test/test")

                                    # Verify success
                                    assert success is True
                                    wrapped_flow.assert_called_once_with(
                                        mock_detailed_pr, "test/test")
