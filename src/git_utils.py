"""
Utility functions for interacting with GitHub API
"""
from typing import List, Dict, Optional, Tuple, Union
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

    # Don't remove signatures with model info, as they should be preserved
    # Only remove duplicate basic signatures if they exist
    basic_signature = r'\n\n---\n\*This response was automatically generated by blech_bot\*\s*$'
    if response.count(basic_signature) > 1:
        # Keep only the first occurrence
        parts = re.split(basic_signature, response)
        response = parts[0] + basic_signature + ''.join(parts[1:])

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
    """Get all open issues and pull requests from repository"""
    return list(repo.get_issues(state='open', sort='created', direction='asc'))


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

    # Check if response already has a signature with model info
    model_signature_pattern = r"\n\n---\n\*This response was automatically generated by blech_bot using model .+\*"
    has_model_signature = bool(
        re.search(model_signature_pattern, response_text))

    # Check if response has the basic signature
    basic_signature = "\n\n---\n*This response was automatically generated by blech_bot*"
    has_basic_signature = basic_signature in response_text

    # Only add signature if no signature exists
    if not has_model_signature and not has_basic_signature:
        # Import the model info from response_agent if available
        try:
            from response_agent import llm_config
            signature = f"\n\n---\n*This response was automatically generated by blech_bot using model {llm_config['model']}*"
        except (ImportError, KeyError):
            signature = basic_signature
        response_text += signature

    return create_issue_comment(issue, response_text)


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


def get_pr_branch(pr: PullRequest) -> str:
    """
    Get the branch name for a pull request

    Args:
        pr: The GitHub pull request to check

    Returns:
        The branch name of the pull request
    """
    return pr.head.ref


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
        out_thread: Issue | PullRequest,
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
        if isinstance(out_thread, Issue):
            issue_comments = list(out_thread.get_comments())
            if 'Failed to push changes' not in issue_comments[-1].body:
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


def get_linked_pr(issue: Issue) -> Optional[PullRequest]:
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


def get_associated_issue(pr: PullRequest) -> Optional[Issue]:
    """
    Get the associated issue for a pull request

    Args:
        pr: The GitHub pull request to check

    Returns:
        The associated Issue object or None if not found
    """

    pr_timeline_events = list(pr.get_timeline())
    # Check if any timeline event is a cross-reference to an issue
    for event in pr_timeline_events:
        if event.event == "cross-referenced":
            # Check if the reference is to an issue
            if event.source:
                for key, val in event.source.raw_data.items():
                    if isinstance(val, dict) and 'issue' in val['html_url']:
                        issue_number = val['number']
                        repo = pr.repository
                        return repo.get_issue(issue_number)

    # # Check if PR body contains "Fixes #X" or "Closes #X" or similar
    # if not pr.body:
    #     return None
    #
    # # Look for common issue reference patterns
    # issue_ref_patterns = [
    #     r"(?:close|closes|closed|fix|fixes|fixed|resolve|resolves|resolved)\s+#(\d+)",
    #     r"(?:issue|issues)\s+#(\d+)",
    #     r"#(\d+)"
    # ]
    #
    # for pattern in issue_ref_patterns:
    #     matches = re.findall(pattern, pr.body, re.IGNORECASE)
    #     if matches:
    #         try:
    #             issue_number = int(matches[0])
    #             return pr.repository.get_issue(issue_number)
    #         except Exception:
    #             continue
    #
    # # If no match found in body, check PR title
    # if pr.title:
    #     for pattern in issue_ref_patterns:
    #         matches = re.findall(pattern, pr.title, re.IGNORECASE)
    #         if matches:
    #             try:
    #                 issue_number = int(matches[0])
    #                 return pr.repository.get_issue(issue_number)
    #             except Exception:
    #                 continue
    #
    return None


def is_pull_request(issue_or_pr: Union[Issue, PullRequest]) -> bool:
    """
    Check if an object is a pull request

    Args:
        issue_or_pr: The GitHub issue or pull request to check

    Returns:
        True if the object is a pull request, False otherwise
    """
    # return hasattr(issue_or_pr, 'merge_commit_sha')
    return 'pull' in issue.html_url


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


def perform_github_search(
        query: str,
        max_snippet_length: int = 2000,  # lines
) -> str:
    """
    Perform a search on GitHub using the provided query and extract code URLs.

    Args:
        query: The search query string.

    Returns:
        A string containing search results with code snippets.
    """
    client = get_github_client()

    try:
        # Search for code with the given query
        search_results = client.search_code(query=query, language='Python')

        # Limit results to avoid rate limiting (GitHub API has limits)
        max_results = 5
        results_str = f"GitHub search results for query: '{query}'\n\n"

        for count, file in enumerate(search_results[:max_results]):

            code_url = file.html_url
            repo_name = file.repository.full_name
            file_path = file.path

            results_str += f"Result {count}:\n"
            results_str += f"Repository: {repo_name}\n"
            results_str += f"File: {file_path}\n"
            results_str += f"URL: {code_url}\n"

            code_snippet = file.decoded_content.decode('utf-8')

            # Truncate very large files
            if len(code_snippet) > max_snippet_length:
                code_snippet = code_snippet[:max_snippet_length] + \
                    "\n... (content truncated, see full file at URL) ..."

                results_str += f"Code snippet:\n```\n{code_snippet}\n```\n\n"

        if count == 0:
            results_str += "No results found for this query."
        elif count == max_results:
            results_str += f"Note: Results limited to {max_results} items. Refine your query for more specific results."

        return results_str

    except Exception as e:
        return f"Error performing GitHub search: {str(e)}"


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
