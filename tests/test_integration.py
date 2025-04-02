"""
Integration tests for the GitHub bot
"""
import os
import sys
import pytest
from unittest.mock import MagicMock, patch
import tempfile
import shutil

# Add src directory to path
src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(src_dir)

from src.response_agent import process_issue, process_repository
from src.git_utils import get_github_client, get_repository


@pytest.mark.integration
@patch('src.git_utils.get_github_client')
@patch('src.git_utils.get_repository')
@patch('src.response_agent.write_issue_response')
def test_process_issue_with_blech_bot_tag(mock_write_response, mock_get_repo, mock_get_client, mock_issue_with_label):
    """Test processing an issue with blech_bot tag"""
    # Setup mocks
    issue = mock_issue_with_label("blech_bot")
    
    # Mock triggers
    with patch('src.triggers.has_bot_response', return_value=False), \
         patch('src.triggers.has_pr_creation_comment', return_value=(False, None)), \
         patch('src.triggers.has_develop_issue_trigger', return_value=False), \
         patch('src.response_agent.generate_new_response', return_value=("Test response", [])):
        
        # Call function
        success, error = process_issue(issue, "test/repo")
        
        # Verify
        assert success is True
        assert error is None
        mock_write_response.assert_called_once()


@pytest.mark.integration
@patch('src.git_utils.get_github_client')
@patch('src.git_utils.get_repository')
def test_process_issue_without_blech_bot_tag(mock_get_repo, mock_get_client, mock_issue):
    """Test processing an issue without blech_bot tag"""
    # Call function
    success, error = process_issue(mock_issue, "test/repo")
    
    # Verify
    assert success is False
    assert "does not have blech_bot label" in error


@pytest.mark.integration
@patch('src.git_utils.get_github_client')
@patch('src.git_utils.get_repository')
@patch('src.response_agent.bot_tools.get_local_repo_path')
@patch('src.branch_handler.checkout_branch')
@patch('src.response_agent.update_repository')
def test_process_repository(mock_update, mock_checkout, mock_get_path, mock_get_repo, mock_get_client, 
                           mock_repository, mock_issue_with_label):
    """Test processing a repository"""
    # Setup mocks
    client = MagicMock()
    mock_get_client.return_value = client
    
    repo = mock_repository
    mock_get_repo.return_value = repo
    
    # Create a temporary directory for the repo
    temp_dir = tempfile.mkdtemp()
    mock_get_path.return_value = temp_dir
    
    # Mock repository having one issue with blech_bot tag
    issue = mock_issue_with_label("blech_bot")
    repo.get_issues.return_value = [issue]
    
    # Mock process_issue to avoid actual processing
    with patch('src.response_agent.process_issue', return_value=(True, None)):
        try:
            # Call function
            process_repository("test/repo")
            
            # Verify
            mock_get_client.assert_called_once()
            mock_get_repo.assert_called_with(client, "test/repo")
            mock_get_path.assert_called_with("test/repo")
            mock_checkout.assert_called_once()
            mock_update.assert_called_once()
        finally:
            # Clean up
            shutil.rmtree(temp_dir)


@pytest.mark.integration
@patch('src.git_utils.get_github_client')
def test_real_github_client(mock_get_client):
    """Test creating a real GitHub client with environment variables"""
    # Setup environment variable
    os.environ['GITHUB_TOKEN'] = 'test-token'
    
    # Mock the Github class
    mock_github = MagicMock()
    mock_get_client.return_value = mock_github
    
    # Call function
    client = get_github_client()
    
    # Verify
    assert client == mock_github
    mock_get_client.assert_called_once()
