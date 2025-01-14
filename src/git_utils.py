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
