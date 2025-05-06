import pytest
from unittest.mock import patch, MagicMock
from src.branch_handler import (
    get_issue_related_branches,
    get_current_branch,
    checkout_branch,
    delete_branch,
    back_to_master_branch,
    push_changes
)


@patch('src.branch_handler.git.Repo')
@patch('src.branch_handler.os.popen')
def test_get_issue_related_branches(mock_popen, mock_repo):
    mock_issue = MagicMock()
    mock_issue.number = 123
    mock_issue.title = "Test Issue"
    mock_popen.return_value.read.return_value = "branch1\turl1\nbranch2\turl2"

    branches = get_issue_related_branches('/path/to/repo', mock_issue)
    expected_branches = [('branch1', 'url1'), ('branch2', 'url2')]
    assert branches == expected_branches

@patch('src.branch_handler.git.Repo')
def test_get_current_branch(mock_repo):
    mock_repo.return_value.active_branch.name = 'main'
    branch_name = get_current_branch('/path/to/repo')
    assert branch_name == 'main'

@patch('src.branch_handler.git.Repo')
def test_checkout_branch(mock_repo):
    mock_repo.return_value.heads = ['main', 'dev']
    checkout_branch('/path/to/repo', 'dev')
    mock_repo.return_value.git.checkout.assert_called_with('dev')

@patch('src.branch_handler.git.Repo')
def test_delete_branch(mock_repo):
    mock_repo.return_value.heads = ['main', 'dev']
    delete_branch('/path/to/repo', 'dev')
    mock_repo.return_value.delete_head.assert_called_with('dev', force=False)

@patch('src.branch_handler.git.Repo')
def test_back_to_master_branch(mock_repo):
    mock_repo.return_value.heads = ['main', 'dev']
    back_to_master_branch('/path/to/repo')
    mock_repo.return_value.git.checkout.assert_called_with('main')

@patch('src.branch_handler.git.Repo')
def test_push_changes(mock_repo):
    mock_repo.return_value.active_branch.name = 'dev'
    push_changes('/path/to/repo')
    mock_repo.return_value.git.push.assert_called_with('origin', 'dev')
