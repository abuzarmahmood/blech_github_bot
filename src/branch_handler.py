"""
Utility functions for handling git branches related to issues
"""
import os
import git
from github.Issue import Issue
from typing import List, Optional, Tuple

def get_issue_related_branches(repo_path: str, issue_number: int) -> List[Tuple[str, bool]]:
    """
    Find all branches (local and remote) related to an issue number
    
    Args:
        repo_path: Path to local git repository
        issue_number: GitHub issue number to search for
    
    Returns:
        List of tuples containing (branch_name, is_remote)
    """
    repo = git.Repo(repo_path)
    related_branches = []
    
    # Check local branches
    for branch in repo.heads:
        if str(issue_number) in branch.name:
            related_branches.append((branch.name, False))
    
    # Check remote branches
    for remote in repo.remotes:
        for ref in remote.refs:
            # Skip HEAD ref
            if ref.name.endswith('/HEAD'):
                continue
            # Remove remote name prefix for comparison
            branch_name = ref.name.split('/', 1)[1]
            if str(issue_number) in branch_name:
                related_branches.append((branch_name, True))
    
    return related_branches

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
    if create and branch_name not in repo.heads:
        repo.create_head(branch_name)
    repo.git.checkout(branch_name)

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
