"""
Agent for generating responses to GitHub issues using pyautogen
"""
from pprint import pprint
from collections.abc import Callable
import random
import traceback
import json
from typing import Optional, Tuple
import os
import subprocess
import autogen
from branch_handler import (
    checkout_branch,
    push_changes,
    back_to_master_branch,
    delete_branch
)
from github.Issue import Issue
from github.Repository import Repository
from git_utils import (
    get_github_client,
    get_repository,
    write_issue_response,
    get_issue_details,
    clone_repository,
    update_repository,
    get_issue_comments,
    create_pull_request_from_issue,
    get_development_branch,
    has_linked_pr,
)
import bot_tools
from autogen import AssistantAgent
import agents
from agents import (
    create_user_agent,
    create_agent,
    generate_prompt,
)
import triggers

from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv('OPENAI_API_KEY')
if not api_key:
    raise ValueError("OpenAI API key not found in environment variables")

llm_config = {
    "model": "gpt-4o",
    "api_key": api_key,
    "temperature": random.uniform(0, 0.2),
}
############################################################
# Response patterns
############################################################


def generate_feedback_response(
        issue: Issue,
        repo_name: str,
        max_turns: int = 10,
) -> Tuple[str, list]:
    """Generate an improved response based on user feedback

    Args:
        repo_name: The name of the repository
        max_turns: Maximum number of turns for the conversation

    Returns:
        Tuple of (updated response text, full conversation history)
    """
    print('===============================')
    print('Generating feedback response')
    print('===============================')
    repo_path = bot_tools.get_local_repo_path(repo_name)
    details = get_issue_details(issue)

    prompt_kwargs = {
        "repo_name": repo_name,
        "repo_path": repo_path,
        "details": details,
        "issue": issue,
    }
    user = create_user_agent()
    feedback_assistant = create_agent("feedback_assistant", llm_config)

    comments = get_issue_comments(issue)
    for comment in reversed(comments):
        if "generated by blech_bot" not in comment.body:
            feedback_text = comment.body
            break
    for comment in reversed(comments):
        if "generated by blech_bot" in comment.body:
            original_response = comment.body
            break

    feedback_prompt = generate_prompt(
        "feedback_assistant",
        **prompt_kwargs,
        original_response=original_response,
        feedback_text=feedback_text,
    )

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

    turns_used = len(feedback_results[0].chat_history)
    updated_response = feedback_results[0].chat_history[-1]['content']
    if turns_used >= max_turns:
        updated_response += f"\n\nNote: The processing was incomplete as the maximum number of turns ({max_turns}) was reached."
    all_content = [original_response, feedback_text, updated_response]
    return updated_response, all_content


def generate_new_response(
        issue: Issue,
        repo_name: str,
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
    summary_assistant = create_agent("summary_assistant", llm_config)
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

    results_to_summarize = [
        [x for x in this_result.chat_history if not bot_tools.is_tool_related(
            x)]
        for this_result in chat_results
    ]
    # Convert to flat list
    results_to_summarize = [
        str(item) for sublist in results_to_summarize for item in sublist]

    if any([len(x) == 0 for x in results_to_summarize]):
        raise ValueError(
            "Got no results to summarize, likely an error in agent responses")

    summary_prompt = generate_prompt(
        "summary_assistant",
        **prompt_kwargs,
        results_to_summarize=results_to_summarize,
    )

    summary_results = summary_assistant.initiate_chat(
        summary_assistant,
        message=summary_prompt,
        max_turns=1,
    )

    turns_used = len(summary_results.chat_history)
    response = summary_results.chat_history[-1]['content']
    if turns_used >= 10:  # Assuming max_turns is 10 here
        response += f"\n\nNote: The processing was incomplete as the maximum number of turns (10) was reached."
    all_content = results_to_summarize + [response]

    return response, all_content


def generate_edit_command_response(
        issue: Issue,
        repo_name: str
) -> Tuple[str, list]:
    """
    Generate a command for a bot to make edits based on issue discussion

    Args:
        issue: The GitHub issue to respond to
        repo_name: Full name of repository (owner/repo)

    Returns:
        Tuple of (response text, conversation history)
    """
    print('===============================')
    print('Generating edit command response')
    print('===============================')

    # Get path to repository and issue details
    repo_path = bot_tools.get_local_repo_path(repo_name)
    details = get_issue_details(issue)

    user = create_user_agent()
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

    turns_used = len(chat_results[0].chat_history)
    response = chat_results[0].chat_history[-1]['content']
    if turns_used >= 10:  # Assuming max_turns is 10 here
        response += f"\n\nNote: The processing was incomplete as the maximum number of turns (10) was reached."
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
    if triggers.has_generate_edit_command_trigger(issue):
        return "generate_edit_command"
    elif triggers.has_user_feedback(issue):
        return "feedback"
    else:
        return "new_response"


def response_selector(trigger: str) -> Callable:
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
            if triggers.has_bot_response(issue) and not triggers.has_user_feedback(issue):
                return False, "Issue already has a bot response without feedback from user"

        # Check for develop_issue trigger first
        if triggers.has_develop_issue_trigger(issue):
            repo_path = bot_tools.get_local_repo_path(repo_name)

            # Check for existing branches
            branch_name = get_development_branch(
                issue, repo_path, create=False)
            if branch_name is not None:
                return False, f"Branch {branch_name} already exists for issue #{issue.number}"

            # Check for linked PRs
            if has_linked_pr(issue):
                return False, f"Issue #{issue.number} already has a linked pull request"

            # Check if issue has label "under_development"
            if "under_development" in [label.name for label in issue.labels]:
                return False, f"Issue #{issue.number} is already under development"

            # First generate edit command from previous discussion
            response, _ = generate_edit_command_response(issue, repo_name)

            branch_name = get_development_branch(issue, repo_path, create=True)
            checkout_branch(repo_path, branch_name, create=False)

            try:
                # Run aider with the generated command
                aider_output = run_aider(response, repo_path)

                # Push changes
                push_changes(repo_path, branch_name)

                # Create pull request
                pr_url = create_pull_request_from_issue(issue, repo_path)
                pr_number = pr_url.split('/')[-1]
                write_issue_response(
                    issue,
                    f"Created pull request: {pr_url}\nContinue discussion there."
                )

                # Mark issue with label "under_development"
                issue.add_to_labels("under_development")

                # Get repo object and pull request
                client = get_github_client()
                repo = get_repository(client, repo_name)
                pull = repo.get_pull(int(pr_number))

                # write_issue_response(issue, "Generated edit command:\n" + response)
                write_str = f"Generated edit command:\n---\n{response}\n\n" + \
                    f"Aider output:\n---\n```{aider_output}```"
                signature = "\n\n---\n*This response was automatically generated by blech_bot*"
                full_response = write_str + signature
                pull.create_issue_comment(full_response)

                # Switch back to main branch
                back_to_master_branch(repo_path)

            except Exception as e:
                # Clean up on error
                back_to_master_branch(repo_path)
                delete_branch(repo_path, branch_name, force=True)
                raise RuntimeError(
                    f"Failed to process develop issue: {str(e)}")

            return True, None

        # Generate and post response
        trigger = check_triggers(issue)
        response_func = response_selector(trigger)
        response, all_content = response_func(issue, repo_name)
        write_issue_response(issue, response)
        return True, None

    except Exception as e:
        return False, f"Error processing issue: {traceback.format_exc()}"


def run_aider(message: str, repo_path: str) -> str:
    """
    Run aider with a given message string

    Args:
        message: The message/instruction to send to aider
        repo_path: Path to the repository to run aider in

    Returns:
        Output from aider command

    Raises:
        subprocess.CalledProcessError: If aider command fails
        FileNotFoundError: If aider is not installed
    """
    try:
        # Change to repo directory
        original_dir = os.getcwd()
        os.chdir(repo_path)

        # Run aider with the message
        result = subprocess.run(
            ['aider', '--yes-always', '--message', message],
            check=True,
            capture_output=True,
            text=True
        )

        # Return to original directory
        os.chdir(original_dir)

        return result.stdout

    except FileNotFoundError:
        raise ValueError(
            "Aider not found. Please install it first with 'pip install aider-chat'")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to run aider: {e.stderr}")


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
