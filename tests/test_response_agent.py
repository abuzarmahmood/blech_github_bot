"""
Tests for response_agent.py
"""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Add src directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from response_agent import (
    generate_new_response,
    generate_feedback_response,
    generate_edit_command_response,
    process_issue,
    check_triggers
)
import bot_tools
import triggers

# Mock environment variables
os.environ['OPENAI_API_KEY'] = 'test_key'

class TestResponseAgent:
    
    @pytest.fixture
    def mock_issue(self):
        """Create a mock issue with blech_bot tag"""
        issue = bot_tools.create_mock_issue(
            title="Test Issue [ blech_bot ]",
            body="This is a test issue",
            labels=["blech_bot"]
        )
        return issue
    
    @pytest.fixture
    def mock_repo(self):
        """Create a mock repository"""
        return bot_tools.create_mock_repository()
    
    @patch('response_agent.create_agent')
    @patch('response_agent.create_user_agent')
    @patch('response_agent.get_issue_details')
    def test_generate_new_response(self, mock_get_details, mock_create_user, mock_create_agent, mock_issue):
        """Test generating a new response"""
        # Setup mocks
        mock_get_details.return_value = {"title": "Test Issue"}
        
        mock_user = MagicMock()
        mock_user.initiate_chats.return_value = [
            MagicMock(chat_history=[{'content': 'Test response'}])
        ]
        mock_create_user.return_value = mock_user
        
        mock_agent = MagicMock()
        mock_agent.initiate_chat.return_value = MagicMock(
            chat_history=[{'content': 'Test summary response'}]
        )
        mock_create_agent.return_value = mock_agent
        
        # Mock bot_tools.get_local_repo_path
        with patch('bot_tools.get_local_repo_path', return_value='/mock/path'):
            # Call the function
            with patch('bot_tools.is_tool_related', return_value=False):
                response, _ = generate_new_response(mock_issue, "test/repo")
        
        # Check the response
        assert "Test summary response" in response
        assert "generated by blech_bot" in response
    
    @patch('response_agent.create_agent')
    @patch('response_agent.create_user_agent')
    @patch('response_agent.get_issue_details')
    @patch('response_agent.get_issue_comments')
    def test_generate_feedback_response(self, mock_get_comments, mock_get_details, mock_create_user, mock_create_agent, mock_issue):
        """Test generating a feedback response"""
        # Setup mocks
        mock_get_details.return_value = {"title": "Test Issue"}
        
        # Create mock comments
        bot_comment = bot_tools.create_mock_comment(
            "Original response\n\n---\n*This response was automatically generated by blech_bot*",
            user_login="blech_bot"
        )
        user_comment = bot_tools.create_mock_comment(
            "User feedback on the response",
            user_login="test_user"
        )
        mock_get_comments.return_value = [bot_comment, user_comment]
        
        mock_user = MagicMock()
        mock_user.initiate_chats.return_value = [
            MagicMock(chat_history=[{'content': 'Updated response based on feedback'}])
        ]
        mock_create_user.return_value = mock_user
        
        mock_agent = MagicMock()
        mock_create_agent.return_value = mock_agent
        
        # Mock bot_tools.get_local_repo_path
        with patch('bot_tools.get_local_repo_path', return_value='/mock/path'):
            # Call the function
            response, _ = generate_feedback_response(mock_issue, "test/repo")
        
        # Check the response
        assert "Updated response based on feedback" in response
        assert "generated by blech_bot" in response
    
    @patch('response_agent.create_agent')
    @patch('response_agent.create_user_agent')
    @patch('response_agent.get_issue_details')
    def test_generate_edit_command_response(self, mock_get_details, mock_create_user, mock_create_agent, mock_issue):
        """Test generating an edit command response"""
        # Setup mocks
        mock_get_details.return_value = {"title": "Test Issue"}
        
        mock_user = MagicMock()
        mock_user.initiate_chats.return_value = [
            MagicMock(chat_history=[{'content': 'Edit command response'}])
        ]
        mock_create_user.return_value = mock_user
        
        mock_agent = MagicMock()
        mock_create_agent.return_value = mock_agent
        
        # Mock bot_tools.get_local_repo_path
        with patch('bot_tools.get_local_repo_path', return_value='/mock/path'):
            # Call the function
            response, _ = generate_edit_command_response(mock_issue, "test/repo")
        
        # Check the response
        assert "Edit command response" in response
        assert "generated by blech_bot" in response
    
    @patch('triggers.has_blech_bot_tag')
    @patch('triggers.has_bot_response')
    @patch('triggers.has_user_feedback')
    @patch('triggers.has_pr_creation_comment')
    @patch('triggers.has_develop_issue_trigger')
    @patch('response_agent.check_triggers')
    @patch('response_agent.response_selector')
    def test_process_issue_new_response(
        self, mock_selector, mock_check_triggers, 
        mock_has_develop, mock_has_pr_comment, 
        mock_has_feedback, mock_has_response, mock_has_tag,
        mock_issue
    ):
        """Test processing an issue that needs a new response"""
        # Setup mocks
        mock_has_tag.return_value = True
        mock_has_response.return_value = False
        mock_has_feedback.return_value = False
        mock_has_pr_comment.return_value = (False, None)
        mock_has_develop.return_value = False
        
        mock_check_triggers.return_value = "new_response"
        
        mock_response_func = MagicMock()
        mock_response_func.return_value = ("Test response", ["content"])
        mock_selector.return_value = mock_response_func
        
        # Call the function with dry_run=True
        with patch('response_agent.write_issue_response') as mock_write:
            success, error, response = process_issue(mock_issue, "test/repo", dry_run=True)
        
        # Check results
        assert success is True
        assert error is None
        assert "Test response" in response
    
    def test_check_triggers(self, mock_issue):
        """Test checking triggers"""
        # Test new response trigger
        with patch('triggers.has_generate_edit_command_trigger', return_value=False):
            with patch('triggers.has_user_feedback', return_value=False):
                with patch('triggers.has_bot_response', return_value=False):
                    assert check_triggers(mock_issue) == "new_response"
        
        # Test feedback trigger
        with patch('triggers.has_generate_edit_command_trigger', return_value=False):
            with patch('triggers.has_user_feedback', return_value=True):
                assert check_triggers(mock_issue) == "feedback"
        
        # Test edit command trigger
        with patch('triggers.has_generate_edit_command_trigger', return_value=True):
            assert check_triggers(mock_issue) == "generate_edit_command"
