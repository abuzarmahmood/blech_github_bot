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


def has_generate_edit_command_trigger(issue: Issue) -> tuple[bool, str]:
    """
    Check if the issue comments contain the trigger for generate_edit_command
    and if the current branch can be pushed

    Args:
        issue: The GitHub issue to check

    Returns:
        Tuple of (trigger_found, error_message)
        - trigger_found: True if the trigger phrase is found in any comment
        - error_message: Error message if branch can't be pushed, empty string otherwise
    """
    from agents import can_push_to_branch
    from git_utils import get_development_branch
    import os

    comments = get_issue_comments(issue)
    trigger_found = any(
        "[ generate_edit_command ]" in comment.body for comment in comments)

    if trigger_found:
        # Get the repository path from the issue
        from bot_tools import get_local_repo_path

        # Extract repo name from issue URL
        repo_name = issue.repository.full_name
        repo_path = get_local_repo_path(repo_name)

        # Check if the branch can be pushed
        branch_name = get_development_branch(issue, repo_path, create=False)
        if branch_name and not can_push_to_branch(repo_path, branch_name):
            return True, f"Cannot push to branch {branch_name}"

    return trigger_found, ""


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

    # find the latest bot comment
    latest_bot_idx = -1
    for i, comment in enumerate(comments):
        if "generated by blech_bot" in comment.body:
            latest_bot_idx = i

    # check if there are any comments after the latest bot comment
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


def has_pr_creation_comment(issue: Issue) -> bool:
    """
    Check if an issue has comments indicating a PR was created

    Args:
        issue: The GitHub issue to check

    Returns:
        True if the issue has PR comments, False otherwise
    """
    comments = get_issue_comments(issue)
    pr_comment_bool = any(
        'Created pull request' in comment.body for comment in comments)
    if pr_comment_bool:
        pr_comment = [
            comment for comment in comments if 'Created pull request' in comment.body][-1]
        return True, pr_comment.body
    else:
        return False, None


def has_error_comment(issue: Issue) -> bool:
    """
    Check if an issue has comments indicating an error

    Args:
        issue: The GitHub issue to check

    Returns:
        True if the issue has error comments, False otherwise
    """
    comments = get_issue_comments(issue)
    return 'Traceback (most recent call last):' in comments[-1].body if comments else False


def has_user_comment_on_pr(issue: Issue) -> bool:
    """
    Check if there is a user comment on a pull request that needs processing

    Args:
        issue: The GitHub issue to check

    Returns:
        True if there is a user comment on a PR that needs processing
    """
    from git_utils import has_linked_pr, get_linked_pr

    # First check issue comments
    comments = get_issue_comments(issue)
    if comments and any("generated by blech_bot" not in comment.body for comment in reversed(comments)):
        return True

    # Then check linked PR comments if available
    try:
        if has_linked_pr(issue):
            pr = get_linked_pr(issue)
            pr_comments = get_issue_comments(pr)

            # Find the latest bot comment
            latest_bot_idx = -1
            for i, comment in enumerate(pr_comments):
                if "generated by blech_bot" in comment.body:
                    latest_bot_idx = i

            # Check if there are any comments after the latest bot comment
            return latest_bot_idx >= 0 and latest_bot_idx < len(pr_comments) - 1
    except:
        # Continue if there's an error getting PR comments
        pass

    return False
