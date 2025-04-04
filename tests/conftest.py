"""
Pytest configuration file with fixtures
"""
import os
import sys
import pytest
from unittest.mock import MagicMock

# Add src directory to path
src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(src_dir)


@pytest.fixture
def mock_issue():
    """Create a mock GitHub issue"""
    issue = MagicMock()
    issue.number = 123
    issue.title = "Test Issue"
    issue.body = "This is a test issue"
    issue.state = "open"
    issue.html_url = "https://github.com/test/repo/issues/123"

    # Add labels
    label = MagicMock()
    label.name = "bug"
    issue.labels = [label]

    return issue


@pytest.fixture
def mock_issue_with_label(label_name="bug"):
    """Create a mock GitHub issue with specific label"""
    def _create_issue(label_name):
        issue = MagicMock()
        issue.number = 123
        issue.title = "Test Issue"
        issue.body = "This is a test issue"
        issue.state = "open"

        # Add label
        label = MagicMock()
        label.name = label_name
        issue.labels = [label]

        return issue

    return _create_issue(label_name)


@pytest.fixture
def mock_pull_request():
    """Create a mock GitHub pull request"""
    pr = MagicMock()
    pr.number = 456
    pr.title = "Test PR"
    pr.body = "This is a test pull request"
    pr.state = "open"
    pr.html_url = "https://github.com/test/repo/pull/456"

    # Add head reference
    head = MagicMock()
    head.ref = "feature-branch"
    pr.head = head

    return pr


@pytest.fixture
def mock_repository():
    """Create a mock GitHub repository"""
    repo = MagicMock()
    repo.full_name = "test/repo"
    repo.name = "repo"
    repo.clone_url = "https://github.com/test/repo.git"
    repo.default_branch = "main"

    return repo


@pytest.fixture
def mock_github_client():
    """Create a mock GitHub client"""
    client = MagicMock()
    return client
