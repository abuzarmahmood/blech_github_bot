import pytest
from src.bot_tools import (
    get_local_repo_path,
    search_for_pattern,
    search_for_file,
    estimate_tokens,
    readfile,
    readlines
)


def test_get_local_repo_path_exists():
    # Assuming a known repo path for testing
    repo_name = "known_owner/known_repo"
    expected_path = "/home/exouser/Desktop/blech_github_bot/src/repos/known_owner/known_repo"
    assert get_local_repo_path(repo_name) == expected_path

def test_get_local_repo_path_not_exists():
    repo_name = "unknown_owner/unknown_repo"
    expected_message = "Repository unknown_owner/unknown_repo not found @ /home/exouser/Desktop/blech_github_bot/src/repos/unknown_owner/unknown_repo"
    assert get_local_repo_path(repo_name) == expected_message

def test_search_for_pattern():
    search_dir = "/home/exouser/Desktop/blech_github_bot/src"
    pattern = "def "
    result = search_for_pattern(search_dir, pattern)
    assert "bot_tools.py" in result

def test_search_for_file_exists():
    directory = "/home/exouser/Desktop/blech_github_bot/src"
    filename = "bot_tools.py"
    result = search_for_file(directory, filename)
    assert "bot_tools.py" in result

def test_search_for_file_not_exists():
    directory = "/home/exouser/Desktop/blech_github_bot/src"
    filename = "non_existent_file.py"
    result = search_for_file(directory, filename)
    assert result == "File not found"

def test_estimate_tokens():
    text = "This is a test sentence."
    assert estimate_tokens(text) == 5

    empty_text = ""
    assert estimate_tokens(empty_text) == 0

def test_readfile():
    filepath = "/home/exouser/Desktop/blech_github_bot/src/bot_tools.py"
    content = readfile(filepath)
    assert "def get_local_repo_path" in content

def test_readlines():
    filepath = "/home/exouser/Desktop/blech_github_bot/src/bot_tools.py"
    content = readlines(filepath, 0, 10)
    assert "def get_local_repo_path" in content
