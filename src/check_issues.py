"""
Main script to check GitHub issues with caching optimization
"""
import os
import sys
from typing import Dict, List

# Add the src directory to the path if needed
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from github import Issue
from git_utils import (
    get_github_client,
    get_repository,
    get_open_issues,
    load_cache_from_file,
    save_cache_to_file
)
from triggers import (
    should_run_detailed_checks,
    has_blech_bot_tag,
    has_generate_edit_command_trigger,
    has_bot_response,
    has_user_feedback,
    has_develop_issue_trigger,
    has_pull_request_trigger,
    has_pr_creation_comment,
    has_user_comment_on_pr
)
from response_agent import process_issue


def check_all_triggers(issue: Issue) -> Dict[str, bool]:
    """
    Run all trigger checks on an issue
    
    Args:
        issue: The GitHub issue to check
        
    Returns:
        Dictionary with trigger names as keys and boolean results as values
    """
    return {
        'has_blech_bot_tag': has_blech_bot_tag(issue),
        'has_generate_edit_command_trigger': has_generate_edit_command_trigger(issue),
        'has_bot_response': has_bot_response(issue),
        'has_user_feedback': has_user_feedback(issue),
        'has_develop_issue_trigger': has_develop_issue_trigger(issue),
        'has_pull_request_trigger': has_pull_request_trigger(issue),
        'has_pr_creation_comment': has_pr_creation_comment(issue)[0],
        'has_user_comment_on_pr': has_user_comment_on_pr(issue)
    }


def main():
    """Main function to check issues with caching optimization"""
    # Load the cache from file
    cache = load_cache_from_file()
    
    # Initialize GitHub client and get repository
    client = get_github_client()
    
    # Get repositories from config file
    repo_names = []
    with open('config/repos.txt', 'r') as f:
        repo_names = [line.strip() for line in f if line.strip()]
    
    for repo_name in repo_names:
        try:
            repo = get_repository(client, repo_name)
            issues = get_open_issues(repo)
            
            print(f"Checking {len(issues)} open issues in {repo_name}")
            
            for issue in issues:
                # Check if we need to run detailed checks
                if should_run_detailed_checks(issue, cache):
                    print(f"Changes detected in issue #{issue.number}, running detailed checks")
                    
                    # Run all trigger checks
                    trigger_results = check_all_triggers(issue)
                    
                    # Process the issue based on trigger results
                    if any(trigger_results.values()):
                        print(f"Processing issue #{issue.number} with active triggers: {[k for k, v in trigger_results.items() if v]}")
                        process_issue(issue, repo_name)
                    else:
                        print(f"No active triggers for issue #{issue.number}")
                else:
                    print(f"No changes detected in issue #{issue.number}, skipping detailed checks")
        
        except Exception as e:
            print(f"Error processing repository {repo_name}: {str(e)}")
    
    # Save the updated cache to file
    save_cache_to_file(cache)
    print("Cache saved successfully")


if __name__ == "__main__":
    main()
