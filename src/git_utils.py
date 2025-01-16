"""
Utility functions for interacting with GitHub API
"""
from typing import List, Dict, Optional
import os
from github import Github
from github.Issue import Issue
from github.Repository import Repository
from github.IssueComment import IssueComment
from dotenv import load_dotenv

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

def create_issue_comment(issue: Issue, comment_text: str) -> IssueComment:
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
    signature = "\n\n---\n*This response was automatically generated by blech_bot*"
    full_response = response_text + signature
    return create_issue_comment(issue, full_response)

def has_blech_bot_tag(issue: Issue) -> bool:
    """
    Check if the issue has the blech_bot tag
    
    Args:
        issue: The GitHub issue to check
        
    Returns:
        True if the issue has the blech_bot tag, False otherwise
    """
    return any(label.name == "blech_bot" for label in issue.labels)

def has_bot_response(issue: Issue) -> bool:
    """
    Check if the latest comment on an issue contains the bot signature
    
    Args:
        issue: The GitHub issue to check
        
    Returns:
        True if the latest comment was from the bot, False otherwise
    """
    comments = get_issue_comments(issue)
    if not comments:
        return False
    latest = comments[-1]
    return "*This response was automatically generated by blech_bot*" in latest.body

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

def clone_repository(repo: Repository, local_path: str) -> str:
    """
    Clone a GitHub repository to local filesystem
    
    Args:
        repo: The GitHub repository to clone
        local_path: Local directory path where repo should be cloned
        
    Returns:
        Path to the cloned repository
    """
    import git
    
    # Create directory if it doesn't exist
    os.makedirs(local_path, exist_ok=True)
    
    # Construct full path for clone
    repo_dir = os.path.join(local_path, repo.name)
    
    # Clone if doesn't exist, or return existing path
    if not os.path.exists(repo_dir):
        git.Repo.clone_from(repo.clone_url, repo_dir)
    
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
