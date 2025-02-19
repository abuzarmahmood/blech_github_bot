"""
Functions to check specific conditions
"""
from github import Issue
from git_utils import get_issue_comments


def has_blech_bot_tag(issue: Issue) -> bool:
    """
    Check if the issue has the blech_bot tag

    Args:
        issue: The GitHub issue to check

    Returns:
        True if the issue has the blech_bot tag, False otherwise
    """
    return any(label.name == "blech_bot" for label in issue.labels)


def has_generate_edit_command_trigger(issue: Issue) -> bool:
    """
    Check if the issue comments contain the trigger for generate_edit_command

    Args:
        issue: The GitHub issue to check

    Returns:
        True if the trigger phrase is found in any comment
    """
    comments = get_issue_comments(issue)
    return any("[ generate_edit_command ]" in comment.body for comment in comments)


def has_bot_response(issue: Issue) -> bool:
    """
    Check if there is already a bot response on the issue

    Args:
        issue: The GitHub issue to check

    Returns:
        True if there is a comment from blech_bot
    """
    comments = get_issue_comments(issue)
    return any("generated by blech_bot" in comment.body for comment in comments)


def has_user_feedback(issue: Issue) -> bool:
    """
    Check if there is user feedback after the latest bot response

    Args:
        issue: The GitHub issue to check

    Returns:
        True if there is a non-bot comment after the latest bot comment
    """
    comments = get_issue_comments(issue)

    # Find the latest bot comment
    latest_bot_idx = -1
    for i, comment in enumerate(comments):
        if "generated by blech_bot" in comment.body:
            latest_bot_idx = i

    # Check if there are any comments after the latest bot comment
    return latest_bot_idx >= 0 and latest_bot_idx < len(comments) - 1


def has_develop_issue_trigger(issue: Issue) -> bool:
    """
    Check if the latest comment contains the develop_issue trigger

    Args:
        issue: The GitHub issue to check

    Returns:
        True if the latest comment contains "[ develop_issue ]"
    """
    comments = get_issue_comments(issue)
    if not comments:
        return False
    return "[ develop_issue ]" in comments[-1].body


def has_reset_development_trigger(issue: Issue) -> bool:
    """
    Check if the latest comment contains the reset_development trigger

    Args:
        issue: The GitHub issue to check

    Returns:
        True if the latest comment contains "[ reset_development ]"
    """
    comments = get_issue_comments(issue)
    if not comments:
        return False
    return "[ reset_development ]" in comments[-1].body

def has_pull_request_trigger(issue: Issue) -> bool:
    """
    Check if the latest comment contains the pull_request trigger

    Args:
        issue: The GitHub issue to check

    Returns:
        True if the latest comment contains "[ pull_request ]"
    """
    comments = get_issue_comments(issue)
    if not comments:
        return False
    return "Created pull request" in comments[-1].body
