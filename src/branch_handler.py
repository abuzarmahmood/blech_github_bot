"""
Utility functions for handling git branches related to issues
"""
import os
import git
from github.Issue import Issue
from typing import List, Optional, Tuple


def get_issue_related_branches(
        repo_path: str,
        issue: Issue
) -> List[Tuple[str, bool]]:
    """
    Uses `gh issue develop -l <issue_number>` to get all branches related to an issue number

    Args:
        repo_path: Path to local git repository
        issue_number: GitHub issue number to search for

    Returns:
        List of tuples containing (branch_name, url)
    """
    issue_number = issue.number

    orig_dir = os.getcwd()
    os.chdir(repo_path)

    related_branches = []
    try:
        branches = os.popen(
            f"gh issue develop -l {issue_number}").read().splitlines()
        for branch in branches:
            # Each line is in the format "branch_name url"
            branch_name = branch.split('\t')[0]
            url = branch.split('\t')[1]
            related_branches.append((branch_name, url))
    except Exception as e:
        print(f"Error getting related branches: {str(e)}")
        # We can't directly log to the issue here as we don't have access to write_issue_response
        # This will be caught by the calling function

    if len(related_branches) == 0:

        repo = git.Repo(repo_path)
        issue_title_cleaned = issue.title.replace(' ', '-').lower()
        # Remove any punctuation from the title
        issue_title_cleaned = ''.join(
            char for char in issue_title_cleaned if char.isalnum() or char == '-' or char == '_')
        possible_branch_name = f"{issue.number}-{issue_title_cleaned}"

        fetched_heads = repo.git.ls_remote('--heads', 'origin').splitlines()

        # Check local branches
        for branch in repo.heads:
            if possible_branch_name in branch.name:
                related_branches.append((branch.name, False))

        for this_head in fetched_heads:
            if possible_branch_name in this_head:
                related_branches.append((this_head.split('heads/')[1], True))

        # Check remote branches
        # for remote in repo.remotes:
        #     for ref in remote.refs:
        #         # Skip HEAD ref
        #         if ref.name.endswith('/HEAD'):
        #             continue
        #         # Remove remote name prefix for comparison
        #         branch_name = ref.name.split('/', 1)[1]
        #         if possible_branch_name in branch_name:
        #             related_branches.append((branch_name, True))

    os.chdir(orig_dir)
    return related_branches

# def get_issue_related_branches(repo_path: str, issue_number: int) -> List[Tuple[str, bool]]:
#     """
#     Find all branches (local and remote) related to an issue number
#
#     Args:
#         repo_path: Path to local git repository
#         issue_number: GitHub issue number to search for
#
#     Returns:
#         List of tuples containing (branch_name, is_remote)
#     """
#     repo = git.Repo(repo_path)
#     related_branches = []
#
#     # Check local branches
#     for branch in repo.heads:
#         if str(issue_number) in branch.name:
#             related_branches.append((branch.name, False))
#
#     # Check remote branches
#     for remote in repo.remotes:
#         for ref in remote.refs:
#             # Skip HEAD ref
#             if ref.name.endswith('/HEAD'):
#                 continue
#             # Remove remote name prefix for comparison
#             branch_name = ref.name.split('/', 1)[1]
#             if str(issue_number) in branch_name:
#                 related_branches.append((branch_name, True))
#
#     return related_branches


def get_current_branch(repo_path: str) -> str:
    """
    Get the name of the current git branch

    Args:
        repo_path: Path to local git repository

    Returns:
        Name of current branch
    """
    repo = git.Repo(repo_path)
    return repo.active_branch.name


def checkout_branch(repo_path: str, branch_name: str, create: bool = False) -> None:
    """
    Checkout a git branch, optionally creating it

    Args:
        repo_path: Path to local git repository
        branch_name: Name of branch to checkout
        create: If True, create branch if it doesn't exist
    """
    repo = git.Repo(repo_path)
    # Get rid of uncommited local changes
    repo.git.clean('-f')
    if create and branch_name not in repo.heads:
        repo.create_head(branch_name)
        print(f"Created branch {branch_name}")
    repo.git.checkout(branch_name)
    print(f"Checked out branch {branch_name}")
    # Force align branch with remote
    repo.git.reset('--hard', f'origin/{branch_name}')
    print(f"Branch {branch_name} aligned with remote")
    # Force align branch with remote
    repo.git.reset('--hard', f'origin/{branch_name}')
    print(f"Branch {branch_name} aligned with remote")


def delete_branch(repo_path: str, branch_name: str, force: bool = False) -> None:
    """
    Delete a git branch

    Args:
        repo_path: Path to local git repository
        branch_name: Name of branch to delete
        force: If True, force delete even if not merged
    """
    repo = git.Repo(repo_path)
    if branch_name in repo.heads:
        repo.delete_head(branch_name, force=force)


def merge_master(repo_path: str, issue=None) -> bool:
    """
    Merge the main/master branch into the current branch with error handling.

    Args:
        repo_path: Path to local git repository
        issue: The GitHub issue to log errors to (optional)

    Returns:
        True if merge was successful, False otherwise
    """
    from src.git_utils import write_issue_response, add_signature_to_comment
    import traceback

    repo = git.Repo(repo_path)
    current_branch = repo.active_branch.name

    # Determine main branch (main or master)
    if 'main' in repo.heads:
        main_branch = 'main'
    elif 'master' in repo.heads:
        main_branch = 'master'
    else:
        error_msg = "Neither 'main' nor 'master' branch found in repository"
        print(error_msg)
        if issue:
            try:
                from response_agent import llm_config
                error_msg_with_signature = add_signature_to_comment(
                    error_msg, llm_config['model'])
            except (ImportError, KeyError):
                error_msg_with_signature = error_msg + \
                    "\n\n---\n*This response was automatically generated by blech_bot*"
            write_issue_response(issue, error_msg_with_signature)
        return False

    # Don't try to merge if we're already on the main branch
    if current_branch == main_branch:
        print(f"Already on {main_branch} branch, no merge needed")
        return True

    try:
        # Make sure main branch is up to date
        repo.git.checkout(main_branch)
        repo.git.pull('origin', main_branch)

        # Go back to feature branch
        repo.git.checkout(current_branch)

        # Merge main into current branch
        repo.git.merge(main_branch)
        print(f"Successfully merged {main_branch} into {current_branch}")
        return True
    except Exception as e:
        error_msg = f"Error merging {main_branch} into {current_branch}: {str(e)}\n\n```\n{traceback.format_exc()}\n```"
        print(error_msg)

        # Try to abort the merge if it's in progress
        try:
            repo.git.merge('--abort')
            print("Merge aborted")
        except:
            print("Could not abort merge, it may not have been in progress")

        # Log error to issue if provided
        if issue:
            try:
                from response_agent import llm_config
                error_msg_with_signature = add_signature_to_comment(
                    error_msg, llm_config['model'])
            except (ImportError, KeyError):
                error_msg_with_signature = error_msg + \
                    "\n\n---\n*This response was automatically generated by blech_bot*"
            write_issue_response(issue, error_msg_with_signature)

        # Make sure we're back on the feature branch
        try:
            repo.git.checkout(current_branch)
        except:
            print(f"Could not checkout {current_branch} after failed merge")

        return False


def back_to_master_branch(repo_path: str) -> None:
    """
    Switch back to master/main branch, detecting which one exists

    Args:
        repo_path: Path to local git repository
    """
    repo = git.Repo(repo_path)

    # Check if master or main branch exists
    if 'master' in repo.heads:
        main_branch = 'master'
    elif 'main' in repo.heads:
        main_branch = 'main'
    else:
        raise ValueError("Neither 'master' nor 'main' branch found")

    # Switch to the main branch
    repo.git.checkout(main_branch)
    print(f"Checked out {main_branch} branch")


def merge_master(repo_path: str, issue=None) -> bool:
    """
    Merge the main/master branch into the current branch with error handling.

    Args:
        repo_path: Path to local git repository
        issue: The GitHub issue to log errors to (optional)

    Returns:
        True if merge was successful, False otherwise
    """
    from src.git_utils import write_issue_response, add_signature_to_comment
    import traceback

    repo = git.Repo(repo_path)
    current_branch = repo.active_branch.name

    # Determine main branch (main or master)
    if 'main' in repo.heads:
        main_branch = 'main'
    elif 'master' in repo.heads:
        main_branch = 'master'
    else:
        error_msg = "Neither 'main' nor 'master' branch found in repository"
        print(error_msg)
        if issue:
            try:
                from response_agent import llm_config
                error_msg_with_signature = add_signature_to_comment(
                    error_msg, llm_config['model'])
            except (ImportError, KeyError):
                error_msg_with_signature = error_msg + \
                    "\n\n---\n*This response was automatically generated by blech_bot*"
            write_issue_response(issue, error_msg_with_signature)
        return False

    # Don't try to merge if we're already on the main branch
    if current_branch == main_branch:
        print(f"Already on {main_branch} branch, no merge needed")
        return True

    try:
        # Make sure main branch is up to date
        repo.git.checkout(main_branch)
        repo.git.pull('origin', main_branch)

        # Go back to feature branch
        repo.git.checkout(current_branch)

        # Merge main into current branch
        repo.git.merge(main_branch)
        print(f"Successfully merged {main_branch} into {current_branch}")
        return True
    except Exception as e:
        error_msg = f"Error merging {main_branch} into {current_branch}: {str(e)}\n\n```\n{traceback.format_exc()}\n```"
        print(error_msg)

        # Try to abort the merge if it's in progress
        try:
            repo.git.merge('--abort')
            print("Merge aborted")
        except:
            print("Could not abort merge, it may not have been in progress")

        # Log error to issue if provided
        if issue:
            try:
                from response_agent import llm_config
                error_msg_with_signature = add_signature_to_comment(
                    error_msg, llm_config['model'])
            except (ImportError, KeyError):
                error_msg_with_signature = error_msg + \
                    "\n\n---\n*This response was automatically generated by blech_bot*"
            write_issue_response(issue, error_msg_with_signature)

        # Make sure we're back on the feature branch
        try:
            repo.git.checkout(current_branch)
        except:
            print(f"Could not checkout {current_branch} after failed merge")

        return False


def push_changes(repo_path: str, branch_name: Optional[str] = None, force: bool = False) -> None:
    """
    Push local changes to remote repository

    Args:
        repo_path: Path to local git repository
        branch_name: Name of branch to push (defaults to current branch)
        force: If True, force push changes
    """
    repo = git.Repo(repo_path)

    # Get current branch if none specified
    if branch_name is None:
        branch_name = repo.active_branch.name

    # Push changes
    if force:
        repo.git.push('origin', branch_name, '--force')
    else:
        repo.git.push('origin', branch_name)
