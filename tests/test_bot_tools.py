"""
Tests for bot_tools.py
"""
import bot_tools
import os
import sys
import pytest
from unittest.mock import patch, mock_open

# Add src directory to path
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '../src')))


class TestBotTools:

    def test_get_local_repo_path(self):
        """Test getting local repo path"""
        with patch('os.path.exists', return_value=True):
            path = bot_tools.get_local_repo_path("owner/repo")
            assert "owner/repo" in path.replace('\\', '/')

    def test_get_tracked_repos(self):
        """Test getting tracked repos"""
        mock_file_content = "owner/repo1\nowner/repo2\n"
        with patch('builtins.open', mock_open(read_data=mock_file_content)):
            repos = bot_tools.get_tracked_repos()
            assert repos == ["owner/repo1", "owner/repo2"]

    def test_create_mock_issue(self):
        """Test creating mock issue"""
        issue = bot_tools.create_mock_issue(
            issue_number=123,
            title="Test Issue",
            body="Test Body",
            labels=["label1", "label2"],
            user_login="test_user"
        )

        assert issue['number'] == 123
        assert issue['title'] == "Test Issue"
        assert issue['body'] == "Test Body"
        assert len(issue['labels']) == 2
        assert issue['labels'][0].name == "label1"
        assert issue['user'].login == "test_user"

        # Test adding labels
        issue['add_to_labels']("label3")
        assert "label3" in [label.name for label in issue['labels']]

    def test_create_mock_comment(self):
        """Test creating mock comment"""
        comment = bot_tools.create_mock_comment(
            body="Test Comment",
            user_login="test_user"
        )

        assert comment['body'] == "Test Comment"
        assert comment['user'].login == "test_user"
        assert comment['created_at'] is not None

    def test_create_mock_repository(self):
        """Test creating mock repository"""
        repo = bot_tools.create_mock_repository(
            name="owner/repo",
            default_branch="main"
        )

        assert repo['name'] == "repo"
        assert repo['full_name'] == "owner/repo"
        assert repo['default_branch'] == "main"

        # Test methods
        assert repo['get_issues']() == []

        # Add an issue and test retrieval
        mock_issue = bot_tools.create_mock_issue()
        repo['issues'].append(mock_issue)
        assert len(repo['get_issues']()) == 1

    def test_search_and_replace(self):
        """Test search and replace function"""
        # Mock file operations
        mock_file_data = "This is a test file\nwith multiple lines\nto test search and replace"

        with patch('builtins.open', mock_open(read_data=mock_file_data)):
            with patch('shutil.copy2') as mock_copy:
                with patch('ast.parse') as mock_parse:
                    # Test successful replacement
                    with patch('builtins.open', mock_open()) as mock_file:
                        result = bot_tools.search_and_replace(
                            "test_file.py",
                            "with multiple lines",
                            "with replaced lines"
                        )
                        assert result is True

                        # Check that file was written with replacement
                        write_handle = mock_file()
                        write_handle.write.assert_called_once()

                        # Check that backup was created
                        mock_copy.assert_called_with(
                            "test_file.py", "test_file.py.bak")

    def test_estimate_tokens(self):
        """Test token estimation function"""
        # Empty text
        assert bot_tools.estimate_tokens("") == 0

        # Simple text
        assert bot_tools.estimate_tokens("This is a test") == 4

        # Longer text
        long_text = "This is a longer test with more tokens to count in the estimation function"
        assert bot_tools.estimate_tokens(long_text) == 14
