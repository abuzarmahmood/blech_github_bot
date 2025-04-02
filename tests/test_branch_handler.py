"""
Tests for the branch_handler module
"""
from src.branch_handler import (
    get_issue_related_branches,
    get_current_branch,
    checkout_branch,
    delete_branch,
    back_to_master_branch,
    push_changes
)
import os
import sys
import pytest
from unittest.mock import MagicMock, patch

# Add src directory to path
src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(src_dir)


@patch('src.branch_handler.os')
@patch('src.branch_handler.git.Repo')
def test_get_issue_related_branches(mock_repo, mock_os):
    """Test finding branches related to an issue"""
    # Setup mocks
    mock_issue = MagicMock()
    mock_issue.number = 123
    mock_issue.title = "Test Issue"

    mock_os.getcwd.return_value = "/original/dir"
    mock_os.popen.return_value.read.return_value = "branch-123\thttp://github.com/test/repo"

    # Call function
    branches = get_issue_related_branches("/path/to/repo", mock_issue)

    # Verify
    mock_os.chdir.assert_any_call("/path/to/repo")
    mock_os.chdir.assert_called_with("/original/dir")
    mock_os.popen.assert_called_with("gh issue develop -l 123")
    assert branches == [("branch-123", "http://github.com/test/repo")]

    # Test fallback when gh command returns no branches
    mock_os.popen.return_value.read.return_value = ""
    mock_repo_instance = MagicMock()
    mock_repo.return_value = mock_repo_instance
    mock_repo_instance.heads = []
    mock_repo_instance.git.ls_remote.return_value = ""

    branches = get_issue_related_branches("/path/to/repo", mock_issue)
    assert branches == []


@patch('src.branch_handler.git.Repo')
def test_get_current_branch(mock_repo):
    """Test getting current branch name"""
    # Setup mock
    mock_repo_instance = MagicMock()
    mock_repo.return_value = mock_repo_instance
    mock_repo_instance.active_branch.name = "test-branch"

    # Call function
    branch = get_current_branch("/path/to/repo")

    # Verify
    mock_repo.assert_called_with("/path/to/repo")
    assert branch == "test-branch"


@patch('src.branch_handler.git.Repo')
def test_checkout_branch(mock_repo):
    """Test branch checkout functionality"""
    # Setup mock
    mock_repo_instance = MagicMock()
    mock_repo.return_value = mock_repo_instance
    mock_repo_instance.heads = ["main"]

    # Test creating new branch
    checkout_branch("/path/to/repo", "test-branch", create=True)

    # Verify
    mock_repo.assert_called_with("/path/to/repo")
    mock_repo_instance.git.clean.assert_called_with('-f')
    mock_repo_instance.create_head.assert_called_with("test-branch")
    mock_repo_instance.git.checkout.assert_called_with("test-branch")
    mock_repo_instance.git.reset.assert_called_with(
        '--hard', 'origin/test-branch')


@patch('src.branch_handler.git.Repo')
def test_delete_branch(mock_repo):
    """Test branch deletion"""
    # Setup mock
    mock_repo_instance = MagicMock()
    mock_repo.return_value = mock_repo_instance
    mock_repo_instance.heads = ["test-branch"]

    # Call function
    delete_branch("/path/to/repo", "test-branch", force=True)

    # Verify
    mock_repo.assert_called_with("/path/to/repo")
    mock_repo_instance.delete_head.assert_called_with(
        "test-branch", force=True)


@patch('src.branch_handler.git.Repo')
def test_back_to_master_branch(mock_repo):
    """Test switching back to master/main branch"""
    # Setup mock
    mock_repo_instance = MagicMock()
    mock_repo.return_value = mock_repo_instance

    # Test with master branch
    mock_repo_instance.heads = ["master", "other"]
    back_to_master_branch("/path/to/repo")
    mock_repo_instance.git.checkout.assert_called_with("master")

    # Test with main branch
    mock_repo_instance.heads = ["main", "other"]
    back_to_master_branch("/path/to/repo")
    mock_repo_instance.git.checkout.assert_called_with("main")

    # Test with neither branch
    mock_repo_instance.heads = ["develop", "other"]
    with pytest.raises(ValueError):
        back_to_master_branch("/path/to/repo")


@patch('src.branch_handler.git.Repo')
def test_push_changes(mock_repo):
    """Test pushing changes to remote"""
    # Setup mock
    mock_repo_instance = MagicMock()
    mock_repo.return_value = mock_repo_instance
    mock_repo_instance.active_branch.name = "test-branch"

    # Test normal push
    push_changes("/path/to/repo")
    mock_repo_instance.git.push.assert_called_with('origin', 'test-branch')

    # Test force push
    push_changes("/path/to/repo", force=True)
    mock_repo_instance.git.push.assert_called_with(
        'origin', 'test-branch', '--force')

    # Test with specific branch
    push_changes("/path/to/repo", branch_name="feature-branch")
    mock_repo_instance.git.push.assert_called_with('origin', 'feature-branch')
