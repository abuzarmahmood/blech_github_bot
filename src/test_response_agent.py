"""
Test script for response_agent.py using Prefect to orchestrate workflows
"""
import os
import sys
from typing import List, Dict, Any

# Add the parent directory to the path so we can import from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from prefect import Flow, task, Parameter
from prefect.engine.results import LocalResult
from prefect.engine.state import State
from prefect.utilities.debug import raise_on_exception

from src.response_agent import (
    generate_feedback_response,
    generate_new_response,
    generate_edit_command_response,
    develop_issue_flow,
    respond_pr_comment_flow,
    standalone_pr_flow,
    check_triggers,
    response_selector,
    process_issue,
    process_repository,
    get_tracked_repos_task,
    initialize_bot_task,
    create_prefect_flow
)

@task
def print_test_header(test_name: str) -> None:
    """Print a header for the test"""
    print(f"\n{'='*80}")
    print(f"TESTING: {test_name}")
    print(f"{'='*80}")

@task
def run_test_with_trigger(repo_name: str, trigger: str) -> None:
    """Run a test with a specific trigger"""
    print(f"Running test with trigger: {trigger}")
    # This would normally get an actual issue, but for testing we'd mock it
    # For now, we'll just print what would happen
    print(f"Would process repository {repo_name} with trigger {trigger}")
    
def create_test_flow() -> Flow:
    """Create a flow for testing all trigger combinations"""
    with Flow("Test Response Agent Triggers") as flow:
        # Get repositories to test with
        repos = get_tracked_repos_task()
        
        # Define triggers to test
        triggers = ["feedback", "generate_edit_command", "new_response", 
                   "develop_issue", "pr_comment", "standalone_pr"]
        
        # Run tests for each combination of repo and trigger
        for repo_name in repos:
            for trigger in triggers:
                header = print_test_header(f"{repo_name} - {trigger}")
                test = run_test_with_trigger(repo_name, trigger)
                test.set_upstream(header)
    
    return flow

if __name__ == "__main__":
    # Run the test flow
    with raise_on_exception():
        flow = create_test_flow()
        flow.run()
    
    # Also demonstrate running the main flow in test mode
    print("\nRunning main flow in test mode...")
    main_flow = create_prefect_flow(test_mode=True)
    main_flow.run()
