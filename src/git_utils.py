"""
Utility functions for interacting with GitHub API
"""
from typing import List, Dict, Optional, Tuple
import os
import subprocess
import git
from branch_handler import (
    get_issue_related_branches,
    get_current_branch,
    checkout_branch,
    delete_branch
)
from github import Github
from github.Issue import Issue
from github.Repository import Repository
from github.IssueComment import IssueComment
from dotenv import load_dotenv
import re

def clean_response(response: str) -> str:
    """Remove any existing signatures or TERMINATE flags from response text"""
    # Remove TERMINATE flags
    response = re.sub(r'\bTERMINATE\b', '', response, flags=re.IGNORECASE)

    # Remove existing signatures
    response = re.sub(
        r'\n\n---\n\*This response was automatically generated by blech_bot\*\s*$', '', response)

    return response.strip()

def get_github_client() -> Github:
    """Initialize and return authenticated GitHub client"""
    load_dotenv()
    token = os.getenv('GITHUB_TOKEN')
    if not token:
        raise ValueError("GitHub token not found in environment variables")
    return Github(token)


def get_repository(client: Github, repo_name: str) -> Repository:
    """Get repository object by full name (owner/repo)"""
    try:
        return client.get_repo(repo_name)
    except Exception as e:
        raise ValueError(f"Could not access repository {repo_name}: {str(e)}")


def get_open_issues(repo: Repository) -> List[Issue]:
    """Get all open issues from repository"""
    return list(repo.get_issues(state='open'))


def get_issue_comments(issue: Issue) -> List[IssueComment]:
    """Get all comments for a specific issue"""
    return list(issue.get_comments())


def create_issue_comment(
        issue: Issue,
        comment_text: str,
) -> IssueComment:
    """Create a new comment on an issue"""
    return issue.create_comment(comment_text)


def get_issue_details(issue: Issue) -> Dict:
    """Extract relevant details from an issue"""
    return {
        'number': issue.number,
        'title': issue.title,
        'body': issue.body,
        'state': issue.state,
        'created_at': issue.created_at,
        'updated_at': issue.updated_at,
        'comments_count': issue.comments,
        'labels': [label.name for label in issue.labels],
        'assignees': [assignee.login for assignee in issue.assignees]
    }


def search_issues(repo: Repository, query: str) -> List[Issue]:
    """Search for issues in repository matching query"""
    return list(repo.get_issues(state='all', labels=[query]))


def write_issue_response(issue: Issue, response_text: str) -> IssueComment:
    """
    Write a response to an issue with the blech_bot signature

    Args:
        issue: The GitHub issue to respond to
        response_text: The text content of the response

    Returns:
        The created comment
    """
    response_text = clean_response(response_text)
    signature = "\n\n---\n*This response was automatically generated by blech_bot*"
    full_response = response_text + signature
    return create_issue_comment(issue, full_response)


def iterate_issues(repo: Repository):
    """
    Generator that yields each issue along with its comments

    Args:
        repo: The GitHub repository to iterate over

    Yields:
        Tuple of (Issue, List[IssueComment])
    """
    issues = get_open_issues(repo)
    for issue in issues:
        comments = get_issue_comments(issue)
        yield issue, comments


def clone_repository(repo: Repository) -> str:
    """
    Clone a GitHub repository to local filesystem

    Args:
        repo: The GitHub repository to clone
        local_path: Local directory path where repo should be cloned

    Returns:
        Path to the cloned repository
    """
    import git

    full_repo_name = repo.full_name
    repo_split = full_repo_name.split('/')
    local_path = os.path.join('repos', repo_split[0])

    # Create directory if it doesn't exist
    os.makedirs(local_path, exist_ok=True)

    # Construct full path for clone
    repo_dir = os.path.join(local_path, repo.name)

    # Clone if doesn't exist, or return existing path
    if not os.path.exists(repo_dir):
        git.Repo.clone_from(repo.clone_url, repo_dir)
        print(f"Cloned repository {full_repo_name} to {repo_dir}")

    return repo_dir


def update_repository(repo_path: str) -> None:
    """
    Pull latest changes for a local repository

    Args:
        repo_path: Path to local git repository
    """
    import git

    git_repo = git.Repo(repo_path)
    origin = git_repo.remotes.origin
    origin.pull()


def get_development_branch(issue: Issue, repo_path: str, create: bool = False) -> str:
    """
    Gets or creates a development branch for an issue

    Args:
        issue: The GitHub issue to create branch for
        repo_path: Path to local git repository
        create: If True, create branch if it doesn't exist

    Returns:
        Name of the branch

    Raises:
        subprocess.CalledProcessError: If gh commands fail
        ValueError: If gh CLI is not installed
        RuntimeError: If multiple branches exist for the issue
    """
    # Check for existing branches related to this issue
    related_branches = get_issue_related_branches(repo_path, issue)
    if len(related_branches) > 1:
        branch_list = "\n".join(
            [f"- {branch_name}" for branch_name in related_branches])
        raise RuntimeError(
            f"Found multiple branches for issue #{issue.number}:\n{branch_list}\n"
            "Please delete or use existing branches before creating a new one."
        )
    elif len(related_branches) == 1:
        return related_branches[0]
    elif create:
        try:
            # Change to repo directory
            original_dir = os.getcwd()
            os.chdir(repo_path)

            # Create branch from issue
            result = subprocess.run(
                ['gh', 'issue', 'develop', str(issue.number)],
                check=True,
                capture_output=True,
                text=True
            )

            related_branch = get_issue_related_branches(
                repo_path, issue)

            # Return to original directory
            os.chdir(original_dir)

            return related_branch[0]

        except FileNotFoundError:
            raise ValueError(
                "GitHub CLI (gh) not found. Please install it first.")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"Failed to create development branch: {e.stderr.strip()}"
            )
    else:
        return None


def create_pull_request(repo_path: str) -> str:
    """
    Creates a pull request from the current branch

    Args:
        repo_path: Path to local git repository

    Returns:
        URL of the created pull request

    Raises:
        subprocess.CalledProcessError: If gh commands fail
        ValueError: If gh CLI is not installed
    """
    try:
        # Change to repo directory
        original_dir = os.getcwd()
        os.chdir(repo_path)

        # Create pull request
        result = subprocess.run(['gh', 'pr', 'create', '--fill'],
                                check=True,
                                capture_output=True,
                                text=True)

        # Return to original directory
        os.chdir(original_dir)

        # Return the PR URL from the output
        return result.stdout.strip()

    except FileNotFoundError:
        raise ValueError("GitHub CLI (gh) not found. Please install it first.")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to create pull request: {e.stderr}")


def create_pull_request_from_issue(issue: Issue, repo_path: str) -> str:
    """
    Creates a pull request from an issue using GitHub CLI

    Args:
        issue: The GitHub issue to create a PR from
        repo_path: Path to local git repository

    Returns:
        URL of the created pull request
    """
    branch = get_development_branch(issue, repo_path)
    return create_pull_request(repo_path)


def push_changes_with_authentication(repo_path: str, branch_name: Optional[str] = None) -> None:
    """
    Push changes to the remote repository with authentication.

    Args:
        repo_path: Path to the local git repository
        branch_name: Name of the branch to push (default: current branch)
    """
    load_dotenv()
    token = os.getenv('GITHUB_TOKEN')

    if not token:
        raise ValueError("GitHub token not found in environment variables")

    repo = git.Repo(repo_path)
    if branch_name is None:
        branch_name = repo.active_branch.name

    remote = repo.remote(name='origin')
    repo_url = remote.url
    if repo_url.startswith('https://'):
        repo_suffix = repo_url.split('github.com/')[-1]
        repo_url_with_token = f"https://x-access-token:{token}@github.com/{repo_suffix}"
        remote.set_url(repo_url_with_token)

    try:
        remote.push(refspec=f'{branch_name}:{branch_name}')
        print(f"Successfully pushed changes to {branch_name}")
    except git.GitCommandError as e:
        raise RuntimeError(f"Error pushing changes: {str(e)}")
    finally:
        if repo_url.startswith('https://'):
            remote.set_url(repo_url)  # Reset URL to remove token


def has_linked_pr(issue: Issue) -> bool:
    """
    Check if an issue has a linked pull request

    Args:
        issue: The GitHub issue to check

    Returns:
        True if the issue has a linked PR, False otherwise
    """
    # Get timeline events to check for PR links
    timeline = list(issue.get_timeline())

    # Check if any timeline event is a cross-reference to a PR
    for event in timeline:
        if event.event == "cross-referenced":
            # Check if the reference is to a PR
            if event.source and event.source.type == "PullRequest":
                return True

    return False


if __name__ == '__main__':
    client = get_github_client()
    repo = get_repository(client, 'katzlabbrandeis/blech_clust')
    issues = get_open_issues(repo)
    print(f"Found {len(issues)} open issues")
    for issue in issues:
        print(get_issue_details(issue))
        comments = get_issue_comments(issue)
        for comment in comments:
            print(f"Comment by {comment.user.login}: {comment.body}")
