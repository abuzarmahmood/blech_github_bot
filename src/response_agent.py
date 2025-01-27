"""
Agent for generating responses to GitHub issues using pyautogen
"""
from pprint import pprint
import json
from typing import Optional, Tuple
import os
import autogen
from github.Issue import Issue
from github.Repository import Repository
from git_utils import (
    get_github_client,
    get_repository,
    has_blech_bot_tag,
    write_issue_response,
    get_issue_details,
    clone_repository,
    update_repository,
    get_issue_comments
)
import bot_tools
from autogen import AssistantAgent
import agents
from agents import (
    create_agents,
    create_summary_agent,
    create_feedback_agent
)

def has_user_feedback(issue: Issue) -> bool:
    """
    Check if there is user feedback after the latest bot response
    
    Args:
        issue: The GitHub issue to check
        
    Returns:
        True if there is a non-bot comment after the latest bot comment
    """
    comments = get_issue_comments(issue)
    
    # Find the latest bot comment
    latest_bot_idx = -1
    for i, comment in enumerate(comments):
        if "generated by blech_bot" in comment.body:
            latest_bot_idx = i
            
    # Check if there are any comments after the latest bot comment
    return latest_bot_idx >= 0 and latest_bot_idx < len(comments) - 1


def generate_feedback_response(
        repo_name: str,
        repo_path: str,
        user: autogen.UserProxyAgent,
        feedback_assistant: AssistantAgent,
        original_response: str,
        feedback_text: str,
        max_turns: int = 10,
        ) -> Tuple[str, list]:
    """Generate an improved response based on user feedback
    
    Args:
        repo_name: The name of the repository
        repo_path: The local path to the repository
        user: The user proxy agent
        feedback_assistant: The feedback processing assistant
        original_response: The original bot response
        feedback_text: The user's feedback text
        
    Returns:
        Tuple of (updated response text, full conversation history)
    """
    feedback_prompt = agents.get_feedback_prompt(repo_name, repo_path, original_response, feedback_text, max_turns)
    
    feedback_results = user.initiate_chats(
        [
            {
                "recipient": feedback_assistant,
                "message": feedback_prompt,
                "max_turns": max_turns,
                "summary_method": "last_msg",
            }
        ]
    )
    
    updated_response = feedback_results[0].chat_history[-1]['content']
    all_content = [original_response, feedback_text, updated_response]
    return updated_response, all_content


def generate_new_response(issue: Issue, repo_name: str) -> Tuple[str, list]:
    """
    Generate a fresh response for a GitHub issue using autogen agents

    Args:
        issue: The GitHub issue to respond to
        repo_name: Full name of repository (owner/repo)

    Returns:
        Tuple of (response text, conversation history)
    """
    # Get path to repository and issue details
    repo_path = bot_tools.get_local_repo_path(repo_name)
    details = get_issue_details(issue)

    # Create base agents
    user, file_assistant, edit_assistant = create_agents()

    # Get prompts and run agents
    file_prompt = agents.get_file_analysis_prompt(repo_name, repo_path, details)
    edit_prompt = agents.get_edit_suggestion_prompt(repo_name, repo_path, details)
    chat_results = user.initiate_chats(
        [
            {
                "recipient": file_assistant,
                "message": file_prompt,
                "max_turns": 10,
                "summary_method": "last_msg",
            },
            {
                "recipient": edit_assistant,
                "message": edit_prompt,
                "max_turns": 10,
                "summary_method": "reflection_with_llm",
            },
        ]
    )

    # Process results
    results_to_summarize = [
        [x for x in this_result.chat_history if 'tool_call' not in str(x)]
        for this_result in chat_results
    ]

    if any([len(x) == 0 for x in results_to_summarize]):
        raise ValueError("Something went wrong with collecting results to summarize")

    # Summarize results
    llm_config = {
        "model": "gpt-4o",
        "api_key": os.getenv('OPENAI_API_KEY'),
        "temperature": 0
    }
    summary_agent = create_summary_agent(llm_config)
    
    summary_results = summary_agent.initiate_chats(
        [
            {
                "recipient": summary_agent,
                "message": f"Summarize the suggestions and changes made by the other agents. Repeat any code snippets as is.\n\n{results_to_summarize}",
                "silent": False,
                "max_turns": 1,
            },
        ]
    )

    response = summary_results[0].chat_history[-1]['content']
    all_content = results_to_summarize + [response]
    
    return response, all_content

def generate_issue_response(
        issue: Issue,
        repo_name: str,
) -> Tuple[str, list]:
    """
    Generate an appropriate response for a GitHub issue using autogen agents

    Args:
        issue: The GitHub issue to respond to
        repo_name: Full name of repository (owner/repo)
        feedback_text: Optional feedback text to process

    Returns:
        Tuple of (response text, conversation history)
    """
    # Handle feedback case
    if has_user_feedback(issue) or feedback_text:
        # Get the latest bot response
        comments = get_issue_comments(issue)
        latest_bot_response = None
        for comment in reversed(comments):
            if "generated by blech_bot" in comment.body:
                latest_bot_response = comment.body
                break
        
        if not latest_bot_response:
            raise ValueError("No bot response found")
            
        # Get latest feedback text if not provided
        if not feedback_text:
            for comment in reversed(comments):
                if "generated by blech_bot" not in comment.body:
                    feedback_text = comment.body
                    break

        # Create feedback agent and process feedback
        llm_config = {
            "model": "gpt-4o",
            "api_key": os.getenv('OPENAI_API_KEY'),
            "temperature": 0
        }
        feedback_assistant = create_feedback_agent(llm_config)
        print('===============================')
        print('Generating feedback response')
        print('===============================')
        return generate_feedback_response(
            repo_name, bot_tools.get_local_repo_path(repo_name),
            create_agents()[0], feedback_assistant, latest_bot_response, feedback_text)
    
    # Generate new response
    print('===============================')
    print('Generating new response')
    print('===============================')
    return generate_new_response(issue, repo_name)


def process_issue(
    issue: Issue,
    repo_name: str,
    ignore_checks: bool = False,
) -> Tuple[bool, Optional[str]]:
    """
    Process a single issue - check if it needs response and generate one

    Args:
        issue: The GitHub issue to process

    Returns:
        Tuple of (whether response was posted, optional error message)
    """
    try:
        # Check if issue has blech_bot tag
        if not has_blech_bot_tag(issue) and not ignore_checks:
            return False, "Issue does not have blech_bot tag"

        # Generate and post response
        response, all_content = generate_issue_response(issue, repo_name)
        write_issue_response(issue, response)
        return True, None

    except Exception as e:
        return False, f"Error processing issue: {str(e)}"


def process_repository(
    repo_name: str,
) -> None:
    """
    Process all open issues in a repository

    Args:
        repo_name: Full name of repository (owner/repo)
    """
    # Initialize GitHub client
    client = get_github_client()
    repo = get_repository(client, repo_name)

    # Ensure repository is cloned and up to date
    repo_dir = clone_repository(repo)
    update_repository(repo_dir)

    # Get open issues
    open_issues = repo.get_issues(state='open')

    # Process each issue
    for issue in open_issues:
        success, error = process_issue(issue, repo_name)
        if success:
            print(f"Successfully processed issue #{issue.number}")
        else:
            print(f"Skipped issue #{issue.number}: {error}")


if __name__ == '__main__':
    # Example usage
    # repo_name = "katzlabbrandeis/blech_clust"
    tracked_repos = bot_tools.get_tracked_repos()
    print(f'Tracked repositories: {tracked_repos}')
    repo_name = tracked_repos[0]
    print(f'Processing repository: {repo_name}')
    # process_repository(repo_name)
    client = get_github_client()
    repo = get_repository(client, repo_name)

    # Ensure repository is cloned and up to date
    repo_dir = clone_repository(repo)
    update_repository(repo_dir)

    # Get open issues
    open_issues = repo.get_issues(state='open')

    # Get all issues which haven't been touched:
    # 1) without a response
    # 2) without the last response being from the bot
    # 3) without an associated branch
    # 4) without an associated PR

    branches = repo.get_branches()
    open_branch_names = [branch.name for branch in branches]

    def branch_checker(branch, issue):
        return str(issue.number) in branch.name or \
            issue.title.lower().replace(" ", "-") in branch.name.lower()

    issue = open_issues[0]
    # generate_issue_response(issue, repo_name)
    process_issue(issue, repo_name)

    # success_list = []
    # max_success = 10
    # for issue in open_issues[:1]:
    #     if len(success_list) > max_success:
    #         print(f"Reached max success limit of {max_success}")
    #         break

    #     # comment_bool = issue.comments == 0
    #     found_branches = [
    #         branch for branch in branches if branch_checker(branch, issue)]

    #     if len(found_branches) == 0:
    #         branch_bool = True
    #     else:
    #         branch_bool = False
    #         print(f"Branch found for issue {issue.number} = {found_branches}")

    #     pr_bool = issue.pull_request is None

    #     fin_bool = bot_bool and branch_bool and pr_bool

    #     if fin_bool:
    #         success, error = process_issue(
    #             issue, repo_name, ignore_checks=True)
    #         if success:
    #             print(f"Successfully processed issue #{issue.number}")
    #             success_list.append(issue.number)
    #         else:
    #             print(f"Skipped issue #{issue.number}: {error}")
