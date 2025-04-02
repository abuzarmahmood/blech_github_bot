"""
Tests for the bot_tools module
"""
import os
import sys
import pytest
from unittest.mock import MagicMock, patch

# Add src directory to path
src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(src_dir)

from src.bot_tools import (
    get_local_repo_path,
    search_for_pattern,
    search_for_file,
    estimate_tokens,
    readfile,
    readlines
)


def test_get_local_repo_path():
    """Test getting local repository path"""
    # Test with existing repo
    with patch('os.path.exists', return_value=True):
        path = get_local_repo_path("owner/repo")
        assert "owner/repo" in path
        assert path.endswith("owner/repo")
    
    # Test with non-existing repo
    with patch('os.path.exists', return_value=False):
        result = get_local_repo_path("nonexistent/repo")
        assert "not found" in result


@patch('os.popen')
def test_search_for_pattern(mock_popen):
    """Test searching for pattern in files"""
    # Setup mock
    mock_popen.return_value.read.return_value = "/path/to/file1.py\n/path/to/file2.py"
    
    # Call function
    result = search_for_pattern("/search/dir", "pattern")
    
    # Verify
    mock_popen.assert_called_with("grep -irl pattern /search/dir --include='*.py'")
    assert result == "/path/to/file1.py\n/path/to/file2.py"


@patch('os.popen')
def test_search_for_file(mock_popen):
    """Test searching for file by name"""
    # Setup mock
    mock_popen.return_value.read.return_value = "/path/to/file.py"
    
    # Call function
    result = search_for_file("/search/dir", "file.py")
    
    # Verify
    mock_popen.assert_called_with("find /search/dir -iname '*file.py*'")
    assert result == "/path/to/file.py"
    
    # Test file not found
    mock_popen.return_value.read.return_value = ""
    result = search_for_file("/search/dir", "nonexistent.py")
    assert result == "File not found"


def test_estimate_tokens():
    """Test token estimation"""
    # Test with normal text
    text = "This is a test string with multiple words."
    assert estimate_tokens(text) == 8
    
    # Test with empty text
    assert estimate_tokens("") == 0
    
    # Test with None
    assert estimate_tokens(None) == 0


@patch('builtins.open')
def test_readfile(mock_open):
    """Test reading file with line numbers"""
    # Setup mock
    mock_file = MagicMock()
    mock_file.__enter__.return_value.readlines.return_value = ["Line 1\n", "Line 2\n", "Line 3\n"]
    mock_open.return_value = mock_file
    
    # Call function
    result = readfile("/path/to/file.py")
    
    # Verify
    mock_open.assert_called_with("/path/to/file.py", 'r')
    assert "0000: Line 1" in result
    assert "0001: Line 2" in result
    assert "0002: Line 3" in result
    
    # Test file not found
    mock_open.side_effect = FileNotFoundError()
    result = readfile("/nonexistent/file.py")
    assert "File not found" in result
    
    # Test other error
    mock_open.side_effect = Exception("Test error")
    result = readfile("/error/file.py")
    assert "Error reading file" in result


@patch('builtins.open')
def test_readlines(mock_open):
    """Test reading specific lines from file"""
    # Setup mock
    mock_file = MagicMock()
    mock_file.__enter__.return_value.readlines.return_value = [
        "Line 1\n", "Line 2\n", "Line 3\n", "Line 4\n", "Line 5\n"
    ]
    mock_open.return_value = mock_file
    
    # Call function
    result = readlines("/path/to/file.py", 1, 4)
    
    # Verify
    mock_open.assert_called_with("/path/to/file.py", 'r')
    assert "0001: Line 2" in result
    assert "0002: Line 3" in result
    assert "0003: Line 4" in result
    assert "0000: Line 1" not in result
    assert "0004: Line 5" not in result
