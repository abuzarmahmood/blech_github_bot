"""
Tests for the response_agent module
"""
import os
import sys
import pytest
from unittest.mock import MagicMock, patch

# Add src directory to path
src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(src_dir)

from src.response_agent import (
    clean_response,
    check_not_empty,
    check_triggers,
    response_selector,
    extract_urls_from_issue,
    scrape_text_from_url,
    summarize_text,
    get_tracked_repos
)


def test_clean_response():
    """Test cleaning response text"""
    # Test removing TERMINATE
    response = "This is a response. TERMINATE"
    cleaned = clean_response(response)
    assert "TERMINATE" not in cleaned
    assert cleaned == "This is a response."
    
    # Test handling model signatures
    response = "Response\n\n---\n*This response was automatically generated by blech_bot using model gpt-4*"
    cleaned = clean_response(response)
    assert cleaned == response
    
    # Test handling basic signatures
    response = "Response\n\n---\n*This response was automatically generated by blech_bot*"
    cleaned = clean_response(response)
    assert cleaned == response


def test_check_not_empty():
    """Test checking if response is not empty"""
    assert check_not_empty("This is a response") is True
    assert check_not_empty("") is False
    assert check_not_empty("terminate") is False
    assert check_not_empty("TERMINATE") is False
    assert check_not_empty("This is a response. TERMINATE") is True


@patch('src.response_agent.triggers')
def test_check_triggers(mock_triggers):
    """Test checking for response triggers"""
    issue = MagicMock()
    
    # Test generate_edit_command trigger
    mock_triggers.has_generate_edit_command_trigger.return_value = True
    mock_triggers.has_user_feedback.return_value = False
    mock_triggers.has_bot_response.return_value = False
    assert check_triggers(issue) == "generate_edit_command"
    
    # Test user feedback trigger
    mock_triggers.has_generate_edit_command_trigger.return_value = False
    mock_triggers.has_user_feedback.return_value = True
    mock_triggers.has_bot_response.return_value = True
    assert check_triggers(issue) == "feedback"
    
    # Test new response trigger
    mock_triggers.has_generate_edit_command_trigger.return_value = False
    mock_triggers.has_user_feedback.return_value = False
    mock_triggers.has_bot_response.return_value = False
    assert check_triggers(issue) == "new_response"
    
    # Test no trigger
    mock_triggers.has_generate_edit_command_trigger.return_value = False
    mock_triggers.has_user_feedback.return_value = False
    mock_triggers.has_bot_response.return_value = True
    assert check_triggers(issue) is None


def test_response_selector():
    """Test selecting response function based on trigger"""
    # Test feedback trigger
    func = response_selector("feedback")
    assert func.__name__ == "generate_feedback_response"
    
    # Test generate_edit_command trigger
    func = response_selector("generate_edit_command")
    assert func.__name__ == "generate_edit_command_response"
    
    # Test new_response trigger
    func = response_selector("new_response")
    assert func.__name__ == "generate_new_response"
    
    # Test invalid trigger
    assert response_selector("invalid") is None


@patch('src.response_agent.get_issue_comments')
def test_extract_urls_from_issue(mock_get_comments):
    """Test extracting URLs from issue and comments"""
    # Setup mock
    issue = MagicMock()
    issue.body = "Issue with URL: https://example.com"
    
    comment1 = MagicMock()
    comment1.body = "Comment with URL: https://github.com"
    comment2 = MagicMock()
    comment2.body = "Another comment with same URL: https://github.com"
    
    mock_get_comments.return_value = [comment1, comment2]
    
    # Call function
    urls = extract_urls_from_issue(issue)
    
    # Verify
    assert len(urls) == 2
    assert "https://example.com" in urls
    assert "https://github.com" in urls


@patch('src.response_agent.requests.get')
def test_scrape_text_from_url(mock_get):
    """Test scraping text content from URL"""
    # Setup mock for HTML response
    mock_response = MagicMock()
    mock_response.text = "<html><body><p>Test content</p></body></html>"
    mock_response.headers = {"Content-Type": "text/html"}
    mock_get.return_value = mock_response
    
    # Call function
    result = scrape_text_from_url("https://example.com")
    
    # Verify
    assert "Test content" in result
    
    # Test non-text content
    mock_response.headers = {"Content-Type": "application/pdf"}
    result = scrape_text_from_url("https://example.com/file.pdf")
    assert "Non-text content detected" in result
    
    # Test request exception
    mock_get.side_effect = Exception("Connection error")
    result = scrape_text_from_url("https://example.com")
    assert "Error fetching URL" in result


def test_summarize_text():
    """Test summarizing text to maximum length"""
    # Test text under max length
    short_text = "This is a short text."
    assert summarize_text(short_text, 100) == short_text
    
    # Test text over max length
    long_text = "This is a very long text that exceeds the maximum length."
    summary = summarize_text(long_text, 20)
    assert len(summary) > 20  # Account for ellipsis and message
    assert "..." in summary
    assert "[Text truncated" in summary


@patch('builtins.open')
def test_get_tracked_repos(mock_open):
    """Test getting tracked repositories"""
    # Setup mock
    mock_file = MagicMock()
    mock_file.__enter__.return_value.readlines.return_value = [
        "owner1/repo1\n", "owner2/repo2\n"
    ]
    mock_open.return_value = mock_file
    
    # Call function
    repos = get_tracked_repos()
    
    # Verify
    assert len(repos) == 2
    assert "owner1/repo1" in repos
    assert "owner2/repo2" in repos
