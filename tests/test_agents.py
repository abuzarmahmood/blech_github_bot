import pytest
from src.agents import register_functions, create_user_agent, create_agent, parse_comments, generate_prompt
from autogen import ConversableAgent, AssistantAgent, UserProxyAgent
from github.Issue import Issue
from unittest.mock import MagicMock


def test_register_functions():
    agent = MagicMock(spec=ConversableAgent)
    registered_agent = register_functions(agent)
    assert isinstance(registered_agent, ConversableAgent)

def test_create_user_agent():
    user_agent = create_user_agent()
    assert isinstance(user_agent, UserProxyAgent)

def test_create_agent():
    agent_name = "edit_assistant"
    llm_config = {"key": "value"}
    agent = create_agent(agent_name, llm_config)
    assert isinstance(agent, AssistantAgent)

def test_parse_comments():
    repo_name = "test_repo"
    repo_path = "/path/to/repo"
    details = {}
    issue = MagicMock(spec=Issue)
    last_comment_str, comments_str, all_comments = parse_comments(
        repo_name, repo_path, details, issue)
    assert isinstance(last_comment_str, str)
    assert isinstance(comments_str, str)
    assert isinstance(all_comments, list)

def test_generate_prompt():
    agent_name = "edit_assistant"
    repo_name = "test_repo"
    repo_path = "/path/to/repo"
    details = {"title": "Test Title", "body": "Test Body"}
    issue = MagicMock(spec=Issue)
    prompt = generate_prompt(
        agent_name, repo_name, repo_path, details, issue)
    assert isinstance(prompt, str)
