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
from github.PullRequest import PullRequest
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
    """Get all comments for a specific issue or pull request"""
    if isinstance(issue, PullRequest):
        return list(issue.get_issue_comments())
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

    unique_branches = set([branch_name for branch_name, _ in related_branches])
    branch_dict = {}
    for branch_name in unique_branches:
        branch_dict[branch_name] = []
        wanted_inds = [i for i, (name, _) in enumerate(
            related_branches) if name == branch_name]
        for ind in wanted_inds:
            branch_dict[branch_name].append(related_branches[ind][1])

    comments = get_issue_comments(issue)

    if len(branch_dict) > 1:
        branch_list = "\n".join(
            [f"- {branch_name} : Remote = {is_remote}"
             for branch_name, is_remote in branch_dict.items()]
        )
        error_msg = f"Found multiple branches for issue #{issue.number}:\n{branch_list}\n" +\
            "Please delete or use existing branches before creating a new one."
        if "Found multiple branches" not in comments[-1].body:
            write_issue_response(issue, error_msg)
        raise RuntimeError(error_msg)
    elif len(branch_dict) == 1:
        return list(branch_dict.keys())[0]
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

            return related_branch[0][0]

        except FileNotFoundError:
            error_msg = "GitHub CLI (gh) not found. Please install it first."
            if error_msg not in comments[-1].body:
                write_issue_response(issue, error_msg)
            raise ValueError(error_msg)
        except subprocess.CalledProcessError as e:
            error_msg = f"Failed to create development branch: {e.stderr.strip()}"
            if "Failed to create" not in comments[-1].body:
                write_issue_response(issue, error_msg)
            raise RuntimeError(error_msg)
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


def push_changes_with_authentication(
        repo_path: str,
        # pull_request: PullRequest,
        out_thread: IssueComment | PullRequest,
        branch_name: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
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
        success_bool = True
    except git.GitCommandError as e:
        error_msg = f"Failed to push changes: {e.stderr.strip()}"
        if isinstance(out_thread, IssueComment):
            write_issue_response(out_thread, error_msg)
        elif isinstance(out_thread, PullRequest):
            pr_comments = list(out_thread.get_issue_comments())
            if 'Failed to push changes' not in pr_comments[-1].body:
                out_thread.create_issue_comment(error_msg)
        else:
            raise ValueError(
                "Invalid output thread type, must be IssueComment or PullRequest")
        print(error_msg)
        success_bool = False
    finally:
        if repo_url.startswith('https://'):
            remote.set_url(repo_url)  # Reset URL to remove token
    if success_bool:
        return success_bool, None
    else:
        return success_bool, error_msg


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


def get_linked_pr(issue: Issue) -> PullRequest:
    """
    Get the linked pull request for an issue

    Args:
        issue: The GitHub issue to check

    Returns:
        The linked PullRequest object or None if not found
    """
    # Get timeline events to check for PR links
    timeline = list(issue.get_timeline())

    # Check if any timeline event is a cross-reference to a PR
    for event in timeline:
        if event.event == "cross-referenced":
            # Check if the reference is to a PR
            if event.source and event.source.type == "PullRequest":
                pr_number = event.source.issue.number
                repo = issue.repository
                return repo.get_pull(pr_number)

    return None


def update_self_repo(
        repo_path: str,
) -> None:
    """
    Pull latest changes for the bot's own repository, handling tracked config files.

    Args:
        repo_path: Path to the bot's local git repository
    """
    import git
    import os
    import shutil

    git_repo = git.Repo(repo_path)
    origin = git_repo.remotes.origin
    # Get repo username/repo_name
    url_splits = git_repo.remotes.origin.url.split('/')[-2:]
    repo_basename = url_splits[-1].split('.')[0]
    repo_name = url_splits[-2] + '/' + repo_basename

    # Initialize GitHub client
    client = get_github_client()
    github_repo = get_repository(client, repo_name)
    # Determine the default branch
    default_branch = github_repo.default_branch

    print(f"Updating self-repo {repo_name}...")

    # Backup config/repos.txt
    config_repos_path = os.path.join(repo_path, 'config', 'repos.txt')
    backup_path = os.path.join(repo_path, 'config', 'repos.txt.backup')

    has_backup = False
    if os.path.exists(config_repos_path):
        print(f"Backing up {config_repos_path}")
        shutil.copy2(config_repos_path, backup_path)
        has_backup = True

    # Fetch latest changes
    print("Fetching latest changes for self-repo")
    origin.fetch()

    # Check if the remote is ahead
    local_commit = git_repo.head.commit
    remote_commit = None
    try:
        remote_commit = origin.refs.master.commit
    except AttributeError:
        try:
            remote_commit = origin.refs.main.commit
        except AttributeError:
            print("Could not find master or main branch on remote")

    if remote_commit and local_commit != remote_commit:
        print("Remote is ahead. Force pulling latest changes for self-repo.")

        # Hard reset to remote branch
        git_repo.git.reset('--hard', f'origin/{default_branch}')
    else:
        print("Self-repo is up-to-date.")

    # Restore config/repos.txt
    if has_backup:
        print(f"Restoring {config_repos_path}")
        shutil.copy2(backup_path, config_repos_path)
        os.remove(backup_path)


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
