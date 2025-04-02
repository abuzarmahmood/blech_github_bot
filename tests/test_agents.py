"""
Tests for the agents module
"""
import os
import sys
import pytest
from unittest.mock import MagicMock, patch

# Add src directory to path
src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(src_dir)

from src.agents import (
    create_user_agent,
    create_agent,
    generate_prompt,
    is_terminate_msg,
    register_functions
)
from autogen import UserProxyAgent, AssistantAgent


def test_create_user_agent():
    """Test creation of user agent"""
    user_agent = create_user_agent()
    assert isinstance(user_agent, UserProxyAgent)
    assert user_agent.name == "User"
    assert user_agent.human_input_mode == "NEVER"


def test_create_agent():
    """Test creation of assistant agent"""
    llm_config = {"model": "test-model", "api_key": "test-key"}
    agent = create_agent("file_assistant", llm_config)
    assert isinstance(agent, AssistantAgent)
    assert agent.name == "file_assistant"
    assert "analyze this GitHub issue" in agent.system_message.lower()


def test_is_terminate_msg():
    """Test terminate message detection"""
    assert is_terminate_msg({"content": "Done. TERMINATE"}) is True
    assert is_terminate_msg({"content": "Not done yet"}) is False
    assert is_terminate_msg({"content": "TERMINATE."}) is True
    assert is_terminate_msg({"content": ""}) is False


@patch('src.agents.parse_comments')
def test_generate_prompt(mock_parse_comments):
    """Test prompt generation for different agent types"""
    # Setup mock
    mock_parse_comments.return_value = ("Last comment", "Comments string", ["comment1"])
    
    # Mock issue and details
    issue = MagicMock()
    issue.number = 123
    issue.title = "Test Issue"
    
    details = {
        "title": "Test Issue",
        "body": "This is a test issue"
    }
    
    # Test file_assistant prompt
    prompt = generate_prompt("file_assistant", "test/repo", "/path/to/repo", details, issue)
    assert "Please analyze this GitHub issue" in prompt
    assert "Repository: test/repo" in prompt
    
    # Test edit_assistant prompt
    prompt = generate_prompt("edit_assistant", "test/repo", "/path/to/repo", details, issue)
    assert "Suggest what changes can be made to resolve this issue" in prompt
    
    # Test feedback_assistant prompt
    prompt = generate_prompt(
        "feedback_assistant", 
        "test/repo", 
        "/path/to/repo", 
        details, 
        issue,
        original_response="Original response",
        feedback_text="Feedback text"
    )
    assert "Process this user feedback" in prompt
    assert "Original response" in prompt
    assert "Feedback text" in prompt


def test_register_functions():
    """Test function registration with agent"""
    agent = MagicMock()
    agent.register_for_llm = MagicMock(return_value=lambda x: x)
    agent.register_for_execution = MagicMock(return_value=lambda x: x)
    
    # Define test function
    def test_func():
        """Test function docstring"""
        pass
    
    # Test LLM registration
    result = register_functions(agent, "llm", [test_func])
    assert agent.register_for_llm.called
    assert agent.register_for_llm.call_args[1]["name"] == "test_func"
    assert "Test function docstring" in agent.register_for_llm.call_args[1]["description"]
    
    # Test execution registration
    agent.reset_mock()
    result = register_functions(agent, "execution", [test_func])
    assert agent.register_for_execution.called
    assert agent.register_for_execution.call_args[1]["name"] == "test_func"
