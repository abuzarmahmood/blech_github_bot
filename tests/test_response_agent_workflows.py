"""
Tests for response_agent.py workflows using Prefect

This test module ensures that all combinations of workflows in response_agent.py
are properly tested using Prefect for orchestration.
"""
import os
import sys
import unittest
from unittest.mock import patch, MagicMock, Mock
import pytest
from prefect import Flow, task
from github.Issue import Issue
from github.PullRequest import PullRequest

# Add the src directory to the path so we can import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.response_agent import (
    check_triggers,
    response_selector,
    process_issue,
    process_repository,
    generate_new_response,
    generate_feedback_response,
    generate_edit_command_response,
    develop_issue_flow,
    respond_pr_comment_flow,
    standalone_pr_flow,
    create_prefect_flow
)
import src.triggers as triggers


class TestResponseAgentWorkflows(unittest.TestCase):
    """Test class for response_agent.py workflows"""

    def setUp(self):
        """Set up test fixtures"""
        # Mock issue
        self.mock_issue = Mock(spec=Issue)
        self.mock_issue.number = 123
        self.mock_issue.title = "Test Issue"
        self.mock_issue.body = "This is a test issue"
        self.mock_issue.labels = []
        
        # Mock PR
        self.mock_pr = Mock(spec=PullRequest)
        self.mock_pr.number = 456
        self.mock_pr.title = "Test PR"
        self.mock_pr.body = "This is a test PR"
        self.mock_pr.labels = []
        
        # Mock repo name
        self.repo_name = "test-owner/test-repo"

    @patch('src.response_agent.triggers.has_generate_edit_command_trigger')
    @patch('src.response_agent.triggers.has_user_feedback')
    @patch('src.response_agent.triggers.has_bot_response')
    def test_check_triggers(self, mock_has_bot_response, mock_has_user_feedback, 
                           mock_has_generate_edit_command_trigger):
        """Test check_triggers function with different trigger combinations"""
        # Test generate_edit_command trigger
        mock_has_generate_edit_command_trigger.return_value = True
        mock_has_user_feedback.return_value = False
        mock_has_bot_response.return_value = False
        
        result = check_triggers(self.mock_issue)
        self.assertEqual(result, "generate_edit_command")
        
        # Test feedback trigger
        mock_has_generate_edit_command_trigger.return_value = False
        mock_has_user_feedback.return_value = True
        mock_has_bot_response.return_value = True
        
        result = check_triggers(self.mock_issue)
        self.assertEqual(result, "feedback")
        
        # Test new_response trigger
        mock_has_generate_edit_command_trigger.return_value = False
        mock_has_user_feedback.return_value = False
        mock_has_bot_response.return_value = False
        
        result = check_triggers(self.mock_issue)
        self.assertEqual(result, "new_response")
        
        # Test no trigger
        mock_has_generate_edit_command_trigger.return_value = False
        mock_has_user_feedback.return_value = False
        mock_has_bot_response.return_value = True
        
        result = check_triggers(self.mock_issue)
        self.assertIsNone(result)

    def test_response_selector(self):
        """Test response_selector function with different triggers"""
        # Test feedback trigger
        result = response_selector("feedback")
        self.assertEqual(result["name"], "feedback")
        self.assertEqual(result["func"], generate_feedback_response)
        
        # Test generate_edit_command trigger
        result = response_selector("generate_edit_command")
        self.assertEqual(result["name"], "generate_edit_command")
        self.assertEqual(result["func"], generate_edit_command_response)
        
        # Test new_response trigger
        result = response_selector("new_response")
        self.assertEqual(result["name"], "new_response")
        self.assertEqual(result["func"], generate_new_response)
        
        # Test none trigger
        result = response_selector(None)
        self.assertEqual(result["name"], "none")
        self.assertIsNone(result["func"])

    @patch('src.response_agent.triggers.has_blech_bot_tag')
    @patch('src.response_agent.is_pull_request')
    @patch('src.response_agent.write_issue_response')
    @patch('src.response_agent.generate_new_response')
    def test_process_issue_new_response(self, mock_generate_new_response, mock_write_issue_response,
                                      mock_is_pull_request, mock_has_blech_bot_tag):
        """Test process_issue function with new_response trigger"""
        # Setup mocks
        mock_is_pull_request.return_value = False
        mock_has_blech_bot_tag.return_value = True
        mock_generate_new_response.return_value = ("Test response", ["content"])
        
        # Patch all trigger checks to simulate new_response trigger
        with patch('src.response_agent.triggers.has_bot_response', return_value=False), \
             patch('src.response_agent.triggers.has_user_feedback', return_value=False), \
             patch('src.response_agent.triggers.has_pr_creation_comment', return_value=(False, None)), \
             patch('src.response_agent.triggers.has_develop_issue_trigger', return_value=False), \
             patch('src.response_agent.triggers.has_error_comment', return_value=False):
            
            result, message = process_issue(self.mock_issue, self.repo_name)
            
            # Verify results
            self.assertTrue(result)
            self.assertIsNone(message)
            mock_generate_new_response.assert_called_once_with(self.mock_issue, self.repo_name)
            mock_write_issue_response.assert_called_once()

    @patch('src.response_agent.triggers.has_blech_bot_tag')
    @patch('src.response_agent.is_pull_request')
    @patch('src.response_agent.write_issue_response')
    @patch('src.response_agent.generate_feedback_response')
    def test_process_issue_feedback(self, mock_generate_feedback_response, mock_write_issue_response,
                                  mock_is_pull_request, mock_has_blech_bot_tag):
        """Test process_issue function with feedback trigger"""
        # Setup mocks
        mock_is_pull_request.return_value = False
        mock_has_blech_bot_tag.return_value = True
        mock_generate_feedback_response.return_value = ("Test feedback response", ["content"])
        
        # Patch all trigger checks to simulate feedback trigger
        with patch('src.response_agent.triggers.has_bot_response', return_value=True), \
             patch('src.response_agent.triggers.has_user_feedback', return_value=True), \
             patch('src.response_agent.triggers.has_pr_creation_comment', return_value=(False, None)), \
             patch('src.response_agent.triggers.has_develop_issue_trigger', return_value=False), \
             patch('src.response_agent.triggers.has_error_comment', return_value=False), \
             patch('src.response_agent.triggers.has_generate_edit_command_trigger', return_value=False):
            
            result, message = process_issue(self.mock_issue, self.repo_name)
            
            # Verify results
            self.assertTrue(result)
            self.assertIsNone(message)
            mock_generate_feedback_response.assert_called_once_with(self.mock_issue, self.repo_name)
            mock_write_issue_response.assert_called_once()

    @patch('src.response_agent.triggers.has_blech_bot_tag')
    @patch('src.response_agent.is_pull_request')
    @patch('src.response_agent.write_issue_response')
    @patch('src.response_agent.generate_edit_command_response')
    def test_process_issue_edit_command(self, mock_generate_edit_command_response, mock_write_issue_response,
                                      mock_is_pull_request, mock_has_blech_bot_tag):
        """Test process_issue function with generate_edit_command trigger"""
        # Setup mocks
        mock_is_pull_request.return_value = False
        mock_has_blech_bot_tag.return_value = True
        mock_generate_edit_command_response.return_value = ("Test edit command", ["content"])
        
        # Patch all trigger checks to simulate generate_edit_command trigger
        with patch('src.response_agent.triggers.has_bot_response', return_value=True), \
             patch('src.response_agent.triggers.has_user_feedback', return_value=False), \
             patch('src.response_agent.triggers.has_pr_creation_comment', return_value=(False, None)), \
             patch('src.response_agent.triggers.has_develop_issue_trigger', return_value=False), \
             patch('src.response_agent.triggers.has_error_comment', return_value=False), \
             patch('src.response_agent.triggers.has_generate_edit_command_trigger', return_value=True):
            
            result, message = process_issue(self.mock_issue, self.repo_name)
            
            # Verify results
            self.assertTrue(result)
            self.assertIsNone(message)
            mock_generate_edit_command_response.assert_called_once_with(self.mock_issue, self.repo_name)
            mock_write_issue_response.assert_called_once()

    @patch('src.response_agent.triggers.has_blech_bot_tag')
    @patch('src.response_agent.is_pull_request')
    @patch('src.response_agent.develop_issue_flow')
    def test_process_issue_develop_issue(self, mock_develop_issue_flow, mock_is_pull_request, mock_has_blech_bot_tag):
        """Test process_issue function with develop_issue trigger"""
        # Setup mocks
        mock_is_pull_request.return_value = False
        mock_has_blech_bot_tag.return_value = True
        mock_develop_issue_flow.return_value = (True, None)
        
        # Patch all trigger checks to simulate develop_issue trigger
        with patch('src.response_agent.triggers.has_bot_response', return_value=True), \
             patch('src.response_agent.triggers.has_user_feedback', return_value=False), \
             patch('src.response_agent.triggers.has_pr_creation_comment', return_value=(False, None)), \
             patch('src.response_agent.triggers.has_develop_issue_trigger', return_value=True), \
             patch('src.response_agent.triggers.has_error_comment', return_value=False):
            
            result, message = process_issue(self.mock_issue, self.repo_name)
            
            # Verify results
            self.assertTrue(result)
            self.assertIsNone(message)
            mock_develop_issue_flow.assert_called_once_with(self.mock_issue, self.repo_name, is_pr=False)

    @patch('src.response_agent.triggers.has_blech_bot_tag')
    @patch('src.response_agent.is_pull_request')
    @patch('src.response_agent.respond_pr_comment_flow')
    def test_process_issue_pr_comment(self, mock_respond_pr_comment_flow, mock_is_pull_request, mock_has_blech_bot_tag):
        """Test process_issue function with PR comment trigger"""
        # Setup mocks
        mock_is_pull_request.return_value = False
        mock_has_blech_bot_tag.return_value = True
        mock_respond_pr_comment_flow.return_value = (True, None)
        
        # Patch all trigger checks to simulate PR comment trigger
        with patch('src.response_agent.triggers.has_bot_response', return_value=True), \
             patch('src.response_agent.triggers.has_user_feedback', return_value=False), \
             patch('src.response_agent.triggers.has_pr_creation_comment', return_value=(True, "PR comment")), \
             patch('src.response_agent.triggers.has_develop_issue_trigger', return_value=False), \
             patch('src.response_agent.triggers.has_error_comment', return_value=False):
            
            result, message = process_issue(self.mock_issue, self.repo_name)
            
            # Verify results
            self.assertTrue(result)
            self.assertIsNone(message)
            mock_respond_pr_comment_flow.assert_called_once_with(self.mock_issue, self.repo_name, "PR comment")

    @patch('src.response_agent.triggers.has_blech_bot_tag')
    @patch('src.response_agent.is_pull_request')
    @patch('src.response_agent.standalone_pr_flow')
    def test_process_issue_standalone_pr(self, mock_standalone_pr_flow, mock_is_pull_request, mock_has_blech_bot_tag):
        """Test process_issue function with standalone PR flow"""
        # Setup mocks
        mock_is_pull_request.return_value = True
        mock_has_blech_bot_tag.return_value = True
        mock_standalone_pr_flow.return_value = (True, None)
        
        # Patch all trigger checks
        with patch('src.response_agent.triggers.has_error_comment', return_value=False):
            
            result, message = process_issue(self.mock_pr, self.repo_name)
            
            # Verify results
            self.assertTrue(result)
            self.assertIsNone(message)
            mock_standalone_pr_flow.assert_called_once_with(self.mock_pr, self.repo_name)

    @patch('src.response_agent.get_github_client')
    @patch('src.response_agent.get_repository')
    @patch('src.response_agent.bot_tools.get_local_repo_path')
    @patch('src.response_agent.clone_repository')
    @patch('src.response_agent.update_repository')
    @patch('src.response_agent.checkout_branch')
    @patch('src.response_agent.process_issue')
    def test_process_repository(self, mock_process_issue, mock_checkout_branch, mock_update_repository,
                              mock_clone_repository, mock_get_local_repo_path, mock_get_repository, 
                              mock_get_github_client):
        """Test process_repository function"""
        # Setup mocks
        mock_repo = MagicMock()
        mock_repo.default_branch = "main"
        mock_repo.get_issues.return_value = [self.mock_issue, self.mock_pr]
        
        mock_get_github_client.return_value = MagicMock()
        mock_get_repository.return_value = mock_repo
        mock_get_local_repo_path.return_value = "/path/to/repo"
        mock_process_issue.return_value = (True, None)
        
        # Test with existing repo
        with patch('os.path.exists', return_value=True):
            process_repository(self.repo_name)
            
            # Verify results
            mock_get_github_client.assert_called_once()
            mock_get_repository.assert_called_once()
            mock_get_local_repo_path.assert_called_once_with(self.repo_name)
            mock_clone_repository.assert_not_called()
            mock_update_repository.assert_called_once()
            mock_checkout_branch.assert_called_once()
            self.assertEqual(mock_process_issue.call_count, 2)
        
        # Reset mocks
        mock_get_github_client.reset_mock()
        mock_get_repository.reset_mock()
        mock_get_local_repo_path.reset_mock()
        mock_clone_repository.reset_mock()
        mock_update_repository.reset_mock()
        mock_checkout_branch.reset_mock()
        mock_process_issue.reset_mock()
        
        # Test with non-existing repo
        with patch('os.path.exists', return_value=False):
            mock_clone_repository.return_value = "/path/to/cloned/repo"
            
            process_repository(self.repo_name)
            
            # Verify results
            mock_get_github_client.assert_called_once()
            mock_get_repository.assert_called_once()
            mock_get_local_repo_path.assert_called_once_with(self.repo_name)
            mock_clone_repository.assert_called_once()
            mock_update_repository.assert_called_once()
            mock_checkout_branch.assert_called_once()
            self.assertEqual(mock_process_issue.call_count, 2)

    def test_create_prefect_flow(self):
        """Test create_prefect_flow function"""
        # Test normal mode
        flow = create_prefect_flow(test_mode=False)
        self.assertIsInstance(flow, Flow)
        self.assertEqual(flow.name, "GitHub Issue Response Flow")
        
        # Test test mode
        flow = create_prefect_flow(test_mode=True)
        self.assertIsInstance(flow, Flow)
        self.assertEqual(flow.name, "GitHub Issue Response Flow")


if __name__ == '__main__':
    unittest.main()
