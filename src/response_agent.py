"""
Agent for generating responses to GitHub issues using pyautogen
"""
from pprint import pprint
import random
import traceback
import json
from typing import Optional, Tuple
import os
import autogen
from github.Issue import Issue
from github.Repository import Repository
from git_utils import (
    get_github_client,
    get_repository,
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
    create_user_agent,
    create_agent,
    gemerate_prompt,
    generate_prompt,
)
import triggers

############################################################
# Trigger checks
############################################################


############################################################
# Response patterns 
############################################################
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
    print('===============================')
    print('Generating feedback response')
    print('===============================')
    prompt_kwargs = {
            "repo_name": repo_name,
            "repo_path": repo_path,
            "details": details,
            "issue": issue,
            }
    feedback_assistant = create_agent("feedback_assistant", llm_config)
    feedback_prompt = generate_prompt(
            "feedback_assistant",
            **prompt_kwargs,
            original_response=original_response,
            feedback_text=feedback_text,
            )
    # feedback_prompt = agents.get_feedback_prompt(
    #     repo_name, repo_path, original_response, feedback_text, max_turns)

    feedback_results = user.initiate_chats(
        [
            {
                "recipient": feedback_assistant,
                "message": feedback_prompt,
                "max_turns": max_turns,
                "summary_method": "reflection_with_llm",
            }
        ]
    )

    updated_response = feedback_results[0].chat_history[-1]['content']
    all_content = [original_response, feedback_text, updated_response]
    return updated_response, all_content


def generate_new_response(
        repo_name: str,
        issue: Issue, 
        ) -> Tuple[str, list]:
    """
    Generate a fresh response for a GitHub issue using autogen agents

    Args:
        issue: The GitHub issue to respond to
        repo_name: Full name of repository (owner/repo)

    Returns:
        Tuple of (response text, conversation history)
    """
    print('===============================')
    print('Generating new response')
    print('===============================')
    # Get path to repository and issue details
    repo_path = bot_tools.get_local_repo_path(repo_name)
    details = get_issue_details(issue)

    # Create base agents
    user = create_user_agent()
    file_assistant = create_agent("file_assistant", llm_config)
    edit_assistant = create_agent("edit_assistant", llm_config)
    summary_agent = create_agent("summary_agent", llm_config)
    # user, file_assistant, edit_assistant = create_agents()

    # Get prompts and run agents
    prompt_kwargs = {
            "repo_name": repo_name,
            "repo_path": repo_path,
            "details": details,
            "issue": issue,
            }
    file_prompt = generate_prompt("file_assistant", **prompt_kwargs)
    edit_prompt = generate_prompt("edit_assistant", **prompt_kwargs)

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

    # Keep everything but tool calls
    def is_tool_related(x):
        if 'tool_calls' in x.keys() or x['role'] == 'tool':
            return True

    results_to_summarize = [
        [x for x in this_result.chat_history if not is_tool_related(x)]
        for this_result in chat_results
    ]

    if any([len(x) == 0 for x in results_to_summarize]):
        raise ValueError(
            "Got no results to summarize, likely an error in agent responses")

    summary_prompt = generate_prompt(
            "summary_agent", 
            **prompt_kwargs,
            results_to_summarize=results_to_summarize,
            )

    summary_results = summary_agent.initiate_chats(
        [
            {
                "recipient": summary_agent,
                "message": summary_prompt, 
                "silent": False,
                "max_turns": 1,
            },
        ]
    )

    response = summary_results[0].chat_history[-1]['content']
    all_content = results_to_summarize + [response]

    return response, all_content

def generate_edit_command_response(issue: Issue, repo_name: str) -> Tuple[str, list]:
    """
    Generate a command for a bot to make edits based on issue discussion

    Args:
        issue: The GitHub issue to respond to
        repo_name: Full name of repository (owner/repo)

    Returns:
        Tuple of (response text, conversation history)
    """
    # Get path to repository and issue details
    repo_path = bot_tools.get_local_repo_path(repo_name)
    details = get_issue_details(issue)

    generate_edit_command_assistant = create_agent(
        "generate_edit_command_assistant", llm_config) 
    generate_edit_command_prompt = generate_prompt(
            "generate_edit_command_assistant", repo_name, repo_path, details, issue)

    chat_results = user.initiate_chats(
        [
            {
                "recipient": generate_edit_command_assistant,
                "message": generate_edit_command_prompt,
                "max_turns": 10,
                "summary_method": "reflection_with_llm",
            },
        ]
    )

    response = chat_results[0].chat_history[-1]['content']
    all_content = [response]
    return response, all_content

############################################################
# Processing logic 
############################################################

def check_triggers(issue: Issue) -> str: 
    """
    Check if the issue contains any triggers for generating a response

    Args:
        issue: The GitHub issue to check

    Returns:
        The trigger phrase found in the issue
    """
    if triggers.has_user_feedback(issue):
        return "feedback"
    elif triggers.has_generate_edit_command_trigger(issue):
        return "generate_edit_command"
    else:
        return "new_response"

def response_selector(trigger: str) -> function: 
    """
    Generate a response for a GitHub issue using autogen agents

    Args:
        trigger: The trigger phrase for generating the response

    Returns:
    """
    if trigger == "feedback":
        return generate_feedback_response
    elif trigger == "generate_edit_command":
        return generate_edit_command_response
    else:
        return generate_new_response

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
        # Check if issue has blech_bot tag or blech_bot in title, and no existing response
        if not ignore_checks:
            has_bot_mention = triggers.has_blech_bot_tag(
                issue) or "[ blech_bot ]" in issue.title.lower()
            if not has_bot_mention:
                return False, "Issue does not have blech_bot tag or mention in title"
            if has_bot_response(issue) and not triggers.has_user_feedback(issue):
                return False, "Issue already has a bot response without feedback from user"

        # Generate and post response
        trigger = check_triggers(issue)
        response_func = response_selector(trigger)
        response, all_content = response_func(issue, repo_name)
        write_issue_response(issue, response)
        return True, None

    except Exception as e:
        return False, f"Error processing issue: {traceback.format_exc()}"


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
    # Get list of repositories to process
    tracked_repos = bot_tools.get_tracked_repos()
    print(f'Found {len(tracked_repos)} tracked repositories')
    pprint(tracked_repos)

    # Process each repository
    for repo_name in tracked_repos:
        print(f'\n=== Processing repository: {repo_name} ===')
        try:
            process_repository(repo_name)
            print(f'Completed processing {repo_name}')
        except Exception as e:
            print(f'Error processing {repo_name}: {str(e)}')
            continue

    print('\nCompleted processing all repositories')
