"""
Agent for generating responses to GitHub issues using pyautogen

3 outcomes types for processing each issue or PR:
    1. Success: Processed successfully and response posted
    2. Skip: Skipped because triggers were not met (e.g., no bot tag, already responded)
    3. Error: An error occurred during processing (e.g., exception thrown)
"""
from typing import Optional, Tuple, List, Union

from dotenv import load_dotenv
import string
import triggers
import traceback
from src.agents import (
    create_user_agent,
    create_agent,
    generate_prompt,
    parse_comments
)
from urlextract import URLExtract
import agents
from autogen import AssistantAgent
import bot_tools
import os

from src.git_utils import (
    get_github_client,
    get_repository,
    write_issue_response,
    get_issue_details,
    clone_repository,
    update_repository,
    get_issue_comments,
    create_pull_request_from_issue,
    get_development_branch,
    push_changes_with_authentication,
    is_pull_request,
    get_pr_branch,
    add_signature_to_comment,
)
from github.Repository import Repository
from github.Issue import Issue
from github.PullRequest import PullRequest
from src.branch_handler import (
    checkout_branch,
    back_to_master_branch,
    delete_branch
)
import autogen
import subprocess
import os
from pprint import pprint
from collections.abc import Callable
import random
import traceback
import json
import re
from urlextract import URLExtract
import requests
import bs4
import git

load_dotenv()
src_dir = os.path.dirname(os.path.abspath(__file__))
base_dir = os.path.dirname(src_dir)

# Read config/params.json
with open(os.path.join(base_dir, 'config', 'params.json')) as f:
    params = json.load(f)

api_key = os.getenv('OPENAI_API_KEY')
if not api_key:
    raise ValueError("OpenAI API key not found in environment variables")

llm_config = {
    "model": "gpt-4o",
    # "model": "o3-mini-2025-01-31",
    "api_key": api_key,
    "temperature": random.uniform(0, 0.2),
}
############################################################
# Response patterns
############################################################


def tab_print(x):
    """
    Print with tab indentation for readability
    """
    """
    Print with tab indentation for readability
    :param x: The object to print
    """
    if isinstance(x, str):
        print('\t' + x)
    elif isinstance(x, dict):
        pprint(x)
    elif isinstance(x, list):
        for item in x:
            print('\t' + str(item))
    else:
        print('\t' + str(x))


def extract_urls_from_issue(issue: Issue) -> List[str]:
    """
    Extract URLs from issue body and comments

    Args:
        issue: The GitHub issue to extract URLs from

    Returns:
        List of URLs found in the issue
    """
    extractor = URLExtract()
    urls = []

    # Extract from issue body
    issue_body = issue.body or ""
    urls.extend(extractor.find_urls(issue_body))

    # Extract from comments
    for comment in get_issue_comments(issue):
        comment_body = comment.body or ""
        urls.extend(extractor.find_urls(comment_body))

    # Remove duplicates while preserving order
    unique_urls = []
    for url in urls:
        if url not in unique_urls:
            unique_urls.append(url)

    return unique_urls


def scrape_text_from_url(url: str) -> str:
    """Scrape text content from a given URL.

    Args:
        url: The URL to scrape text from.

    Returns:
        The scraped text content or a message if non-text content is detected.
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # Raise an error for bad responses

        # Check if the content type is text-based
        content_type = response.headers.get('Content-Type', '')
        if 'text' not in content_type and 'html' not in content_type and 'json' not in content_type:
            return f"Non-text content detected at URL {url}: {content_type}"

        soup = bs4.BeautifulSoup(response.text, 'html.parser')

        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.extract()

        # Get text
        text = soup.get_text()

        # Break into lines and remove leading and trailing space on each
        lines = (line.strip() for line in text.splitlines())
        # Break multi-headlines into a line each
        chunks = (phrase.strip()
                  for line in lines for phrase in line.split("  "))
        # Remove blank lines
        text = '\n'.join(chunk for chunk in chunks if chunk)

        return text
    except requests.RequestException as e:
        tab_print(f"Error fetching URL {url}: {e}")
        return f"Error fetching URL {url}: {str(e)}"


def summarize_text(text: str, max_length: int = 1000) -> str:
    """Summarize text using a summary agent.

    Args:
        text: The text to summarize.
        max_length: Maximum length of the summary.

    Returns:
        The summarized text.
    """
    if len(text) <= max_length:
        return text

    # Use summary agent to create a contextually relevant summary
    summary_agent = create_agent("summary_agent", llm_config)

    # Create a prompt for the summary agent
    summary_prompt = f"""
    Please summarize the following text, focusing on the most relevant information.
    Maintain all technical details and important context that would be relevant to the issue.
    Prioritize code-related information, error messages, and specific technical requirements.

    TEXT TO SUMMARIZE:
    {text}
    """

    # Get summary from the agent
    summary_results = summary_agent.initiate_chat(
        summary_agent,
        message=summary_prompt,
        max_turns=1,
        silent=params['print_llm_output']
    )

    # Extract the summary from the response
    summary = summary_results.chat_history[-1]['content']

    return summary


def get_tracked_repos() -> str:
    """
    Get the tracked repositories

    Returns:
        - List of tracked repositories
    """
    tracked_repos_path = os.path.join(base_dir, 'config', 'repos.txt')
    with open(tracked_repos_path, 'r') as file:
        tracked_repos = file.readlines()
    tracked_repos = [repo.strip() for repo in tracked_repos]
    return tracked_repos

# Keep everything but tool calls


def is_tool_related(
        x: dict,) -> bool:
    if 'tool_calls' in x.keys() or x['role'] == 'tool':
        return True


def check_not_empty(data: str) -> bool:
    """
    Check that given data is not empty and is not a TERMINATE message
    """
    clean_data = data.translate(str.maketrans('', '', string.punctuation))
    clean_data = clean_data.lower()
    if clean_data != '' and clean_data != 'terminate':
        return True
    else:
        return False


def clean_response(response: str) -> str:
    """
    Remove any existing signatures or TERMINATE flags from response text

    Args:
        response: The response text to clean

    Returns:
        Cleaned response text without signatures or TERMINATE flags
    """
    # Remove TERMINATE flags
    response = re.sub(r'\bTERMINATE\b', '', response, flags=re.IGNORECASE)

    # Remove model-specific signatures
    model_signature_pattern = r'\n\n---\n\*This response was automatically generated by blech_bot using model .+\*\s*$'
    response = re.sub(model_signature_pattern, '', response)

    # Remove basic signatures
    basic_signature = r'\n\n---\n\*This response was automatically generated by blech_bot\*\s*$'
    response = re.sub(basic_signature, '', response)

    return response.strip()


def summarize_relevant_comments(
        issue: Issue,
        repo_name: str,
) -> Tuple[str, list]:
    """Summarize relevant comments for a given issue

    Args:
        issue: The GitHub issue to summarize
        repo_name: Full name of repository (owner/repo)
        max_turns: Maximum number of turns for the conversation

    Returns:
        Tuple of (summary text, full conversation history)
    """
    repo_path = bot_tools.get_local_repo_path(repo_name)
    details = get_issue_details(issue)

    # user, file_assistant, edit_assistant = create_agents()
    last_comment, comment_str, comment_list = parse_comments(
        repo_name, repo_path, details, issue)

    prompt_kwargs = {
        "repo_name": repo_name,
        "repo_path": repo_path,
        "details": details,
        "issue": issue,
    }

    comment_summary_assistant = create_agent(
        "comment_summary_assistant", llm_config)
    summarized_comments = []
    for comment in comment_list[:-1]:
        summary_prompt = generate_prompt(
            "comment_summary_assistant",
            **prompt_kwargs,
            # original_response=comment_list[-1],
            feedback_text=comment_list[-1],
            results_to_summarize=[comment],
        )

        chat_config = dict(
            recipient=comment_summary_assistant,
            message=summary_prompt,
            max_turns=1,
            silent=params['print_llm_output']
        )
        comment_summary_results = comment_summary_assistant.initiate_chat(
            **chat_config)

        response = comment_summary_results.chat_history[-1]['content']
        summarized_comments.append(response)

    # Remove all mentioned of "IS_RELEVANT", "NOT_RELEVANT", and "TERMINATE" from the summaries
    # Keep them in the code for future reference
    summarized_comments = [re.sub(r'\bIS_RELEVANT\b', '', comment)
                           for comment in summarized_comments]
    summarized_comments = [re.sub(r'\bNOT_RELEVANT\b', '', comment)
                           for comment in summarized_comments]
    summarized_comments = [re.sub(r'\bTERMINATE\b', '', comment)
                           for comment in summarized_comments]
    # Make sure to remove any empty strings and new lines
    summarized_comments = [comment.strip() for comment in summarized_comments]
    # Keep only comments with content
    summarized_comments = [comment for comment in summarized_comments if check_not_empty(
        comment)]

    summary_comment_str = '\n====================================================\n'.join(
        summarized_comments)

    return summarized_comments, comment_list, summary_comment_str


def generate_feedback_response(
        issue: Issue,
        repo_name: str,
        max_turns: int = 20,
) -> Tuple[str, list]:
    """Generate an improved response based on user feedback

    Args:
        repo_name: The name of the repository
        max_turns: Maximum number of turns for the conversation

    Returns:
        Tuple of (updated response text, full conversation history)
    """
    tab_print('===============================')
    tab_print('Generating feedback response')
    tab_print('===============================')
    repo_path = bot_tools.get_local_repo_path(repo_name)
    details = get_issue_details(issue)

    # Extract URLs from issue and scrape content
    urls = extract_urls_from_issue(issue)
    url_contents = {}

    if urls:
        tab_print(f"Found {len(urls)} URLs in issue")
        for url in urls:
            tab_print(f"Scraping content from {url}")
            content = scrape_text_from_url(url)
            # Summarize content to avoid token limits
            summarized_content = summarize_text(content)
            url_contents[url] = summarized_content

        # Add URL contents to issue details
        details['url_contents'] = url_contents

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

    chat_config = dict(
        recipient=feedback_assistant,
        message=feedback_prompt,
        max_turns=max_turns,
        summary_method="reflection_with_llm",
        silent=params['print_llm_output']
    )
    feedback_results = user.initiate_chats([chat_config])

    for this_chat in feedback_results[0].chat_history[::-1]:
        this_content = this_chat['content']
        if check_not_empty(this_content):
            updated_response = this_content
            break
    all_content = [original_response, feedback_text, updated_response]
    # Clean the response first to remove any existing signatures
    updated_response = clean_response(updated_response)
    signature = f"\n\n---\n*This response was automatically generated by blech_bot using model {llm_config['model']}*"
    if signature not in updated_response:
        updated_response += signature
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
    tab_print('===============================')
    tab_print('Generating new response')
    tab_print('===============================')
    # Get path to repository and issue details
    repo_path = bot_tools.get_local_repo_path(repo_name)
    details = get_issue_details(issue)

    # Extract URLs from issue and scrape content
    urls = extract_urls_from_issue(issue)
    url_contents = {}

    if urls:
        tab_print(f"Found {len(urls)} URLs in issue")
        for url in urls:
            tab_print(f"Scraping content from {url}")
            content = scrape_text_from_url(url)
            # Summarize content to avoid token limits
            summarized_content = summarize_text(content)
            url_contents[url] = summarized_content

        # Add URL contents to issue details
        details['url_contents'] = url_contents

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

    chat_configs = [
        dict(
            recipient=file_assistant,
            message=file_prompt,
            max_turns=20,
            summary_method="last_msg",
            silent=params['print_llm_output']
        ),
        dict(
            recipient=edit_assistant,
            message=edit_prompt,
            max_turns=20,
            summary_method="reflection_with_llm",
            silent=params['print_llm_output']
        ),
    ]

    chat_results = user.initiate_chats(chat_configs)

    results_to_summarize = [
        [x for x in this_result.chat_history if not is_tool_related(
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
        silent=params['print_llm_output']
    )

    response = summary_results.chat_history[-1]['content']
    all_content = results_to_summarize + [response]

    # Clean the response first to remove any existing signatures
    response = clean_response(response)
    signature = f"\n\n---\n*This response was automatically generated by blech_bot using model {llm_config['model']}*"
    if signature not in response:
        response += signature
    return response, all_content


def generate_edit_command_response(
        issue: Issue,
        repo_name: str,
        summarized_comments: str = '',
) -> Tuple[str, list]:
    """
    Generate a command for a bot to make edits based on issue discussion

    Args:
        issue: The GitHub issue to respond to
        repo_name: Full name of repository (owner/repo)

    Returns:
        Tuple of (response text, conversation history)
    """
    tab_print('===============================')
    tab_print('Generating edit command response')
    tab_print('===============================')

    # Get path to repository and issue details
    repo_path = bot_tools.get_local_repo_path(repo_name)
    details = get_issue_details(issue)

    # Extract URLs from issue and scrape content
    urls = extract_urls_from_issue(issue)
    url_contents = {}

    if urls:
        tab_print(f"Found {len(urls)} URLs in issue")
        for url in urls:
            tab_print(f"Scraping content from {url}")
            content = scrape_text_from_url(url)
            # Summarize content to avoid token limits
            summarized_content = summarize_text(content)
            url_contents[url] = summarized_content

        # Add URL contents to issue details
        details['url_contents'] = url_contents

    user = create_user_agent()
    generate_edit_command_assistant = create_agent(
        "generate_edit_command_assistant", llm_config)
    if summarized_comments:
        generate_edit_command_prompt = generate_prompt(
            "generate_edit_command_assistant",
            repo_name, repo_path, details, issue,
            summarized_comments_str=summarized_comments
        )
    else:
        generate_edit_command_prompt = generate_prompt(
            "generate_edit_command_assistant",
            repo_name, repo_path, details, issue
        )

    chat_config = dict(
        silent=params['print_llm_output'],
        recipient=generate_edit_command_assistant,
        message=generate_edit_command_prompt,
        max_turns=20,
        summary_method="reflection_with_llm",
    )
    chat_results = user.initiate_chats([chat_config])

    for this_chat in chat_results[0].chat_history[::-1]:
        this_content = this_chat['content']
        if check_not_empty(this_content):
            response = this_content
            break
    all_content = [response]
    # Clean the response first to remove any existing signatures
    response = clean_response(response)
    signature = f"\n\n---\n*This response was automatically generated by blech_bot using model {llm_config['model']}*"
    if signature not in response:
        response += signature
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
        tab_print('Triggered by generate_edit_command')
        return "generate_edit_command"
    elif triggers.has_user_feedback(issue):
        tab_print('Triggered by user feedback')
        return "feedback"
    elif not triggers.has_bot_response(issue):
        tab_print('Triggered by new issue')
        return "new_response"
    else:
        return None


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
    elif trigger == "new_response":
        return generate_new_response
    else:
        return None


def write_pr_comment(
        pr_obj: PullRequest,
        response: str,
        aider_output: str,
        llm_config: dict,
        write_str: str = None,
) -> None:
    """
    Write a comment on the pull request with the generated response and aider output

    Args:
        pr_obj: The PullRequest object to write the comment on
        response: The generated response text
        aider_output: The output from the aider command
        llm_config: The configuration for the LLM used to generate the response
    """
    # Clean the response first to remove any existing signatures
    write_str = clean_response(response)
    signature = f"\n\n---\n*This response was automatically generated by blech_bot using model {llm_config['model']}*"
    if signature not in write_str:
        write_str += signature
    pr_obj.create_issue_comment(write_str)


def develop_issue_flow(
        issue_or_pr: Union[Issue, PullRequest],
        repo_name: str,
        is_pr: bool = False,
) -> Tuple[bool, Optional[str]]:
    # Only issues can be developed, not PRs
    if is_pr:
        return False, "Cannot develop a PR, only issues can be developed"

    tab_print('Triggered by [ develop_issue ] command')
    repo_path = bot_tools.get_local_repo_path(repo_name)

    # Check for existing branches
    branch_name = get_development_branch(
        issue_or_pr, repo_path, create=False)

    # Check if issue has label "under_development"
    if "under_development" in [label.name for label in issue_or_pr.labels]:
        return False, f"Issue #{issue_or_pr.number} is already under development"

    # First generate edit command from previous discussion
    response, _ = generate_edit_command_response(
        issue_or_pr, repo_name)

    branch_name = get_development_branch(
        issue_or_pr, repo_path, create=True)
    original_dir = os.getcwd()
    os.chdir(repo_path)
    checkout_branch(repo_path, branch_name, create=False)

    try:
        # Run aider with the generated command
        aider_output = run_aider(response, repo_path)

        # Get repo object and pull request
        client = get_github_client()
        repo = get_repository(client, repo_name)

        # Push changes with authentication
        push_changes_with_authentication(
            repo_path,
            issue_or_pr,
            branch_name
        )

        pr_url = create_pull_request_from_issue(issue_or_pr, repo_path)
        pr_number = pr_url.split('/')[-1]
        pull = repo.get_pull(int(pr_number))

        # Create pull request
        write_issue_response(
            issue_or_pr,
            f"Created pull request: {pr_url}\nContinue discussion there."
        )

        # Mark issue with label "under_development"
        issue_or_pr.add_to_labels("under_development")

        # write_issue_response(issue, "Generated edit command:\n" + response)
        write_str = f"Generated edit command:\n---\n{response}\n\n" + \
            f"Aider output:\n<details><summary>View Aider Output</summary>\n\n```{aider_output}```\n</details>"
        write_pr_comment(
            pull,
            write_str,
            aider_output=aider_output,
            llm_config=llm_config,
            write_str=write_str
        )

        # Switch back to main branch
        back_to_master_branch(repo_path)
        # Return to original directory
        os.chdir(original_dir)

    except Exception as e:
        # Clean up on error
        try:
            back_to_master_branch(repo_path)
            delete_branch(repo_path, branch_name, force=True)
            clean_error_msg = ""
        except Exception as cleanup_error:
            clean_error_msg = f"ERROR during cleanup: {str(cleanup_error)}"
            tab_print(clean_error_msg)

        # Return to original directory
        os.chdir(original_dir)

        # Log detailed error to the issue with signature
        error_msg = f"ERROR: Failed to process develop issue: {str(e)}\n\n```\n{traceback.format_exc()}\n```"
        if clean_error_msg:
            error_msg += f"\n\n{clean_error_msg}"
        tab_print(f"Error logged to issue: {error_msg}")
        raise Exception(error_msg)

    return True, None


def respond_pr_comment_flow(
        issue_or_pr: Union[Issue, PullRequest],
        repo_name: str,
        pr_comment: str,
) -> Tuple[bool, Optional[str]]:

    try:
        tab_print("Attempting to get PR branch details")
        repo_path = bot_tools.get_local_repo_path(repo_name)
        repo = get_repository(get_github_client(), repo_name)

        # Get latest user comment
        extractor = URLExtract()
        urls = extractor.find_urls(pr_comment)[0]
        pr_number = int(urls.split('/')[-1])
        pr = repo.get_pull(pr_number)

        # comments = list(pr.get_issue_comments())
        # Use the helper function to get comments to filter graphite comments
        comments = get_issue_comments(pr)

        if not comments:
            tab_print(f"No comments found on the PR# {pr_number}")
            tab_print(
                "If PR was generated using `develop_issue`, something went wrong.")

        # find the latest bot comment
        latest_bot_idx = -1
        for i, comment in enumerate(comments):
            if "generated by blech_bot" in comment.body:
                latest_bot_idx = i

        # check if there are any comments after the latest bot comment
        user_feedback_bool = latest_bot_idx >= 0 and latest_bot_idx < len(
            comments) - 1

        # branch_name = get_development_branch(
        #     issue_or_pr, repo_path, create=False)
        branch_name = get_pr_branch(pr)
        tab_print(f"Found branch name: {branch_name}")

    except Exception as e:
        pr_msg = f"ERROR: Failed to process PR {pr_number} comment flow: {str(e)}\n\n```\n{traceback.format_exc()}\n```"
        tab_print(pr_msg)
        raise Exception(pr_msg)

    # Only run if branch exists and user comment is found on PR
    if branch_name and user_feedback_bool:
        user_comment = comments[-1].body
        tab_print(f'Triggered by user comment on PR #{pr_number}')

        try:
            original_dir = os.getcwd()
            os.chdir(repo_path)
            # Switch to development branch
            checkout_branch(repo_path, branch_name, create=False)

            # Might have to pull and merge here if pre-commit hooks are enabled
            # and made changes
            remote_branch = f"origin/{branch_name}"
            subprocess.run(
                ['git', 'pull', 'origin', branch_name], check=True)

            if user_comment:
                # Summarize relevant comments
                summarized_comments, comment_list, summary_comment_str = summarize_relevant_comments(
                    issue_or_pr, repo_name)

                if summary_comment_str == '':
                    summary_comment_str = 'No relevant comments found'

                # Pass to generate_edit_command agent first
                response, _ = generate_edit_command_response(
                    issue_or_pr, repo_name, summary_comment_str)

                # Then run aider with the generated command
                aider_output = run_aider(response, repo_path)

                # Push changes
                push_changes_with_authentication(
                    repo_path,
                    pr,
                    branch_name)

                # Write response
                write_str = f"Applied changes based on comment:\n<details><summary>View Aider Output</summary>\n\n```\n{aider_output}\n```\n</details>"
                write_pr_comment(
                    pr,
                    write_str,
                    aider_output=aider_output,
                    llm_config=llm_config,
                    write_str=write_str
                )

                # Clean up
                back_to_master_branch(repo_path)

                # Return to original directory
                os.chdir(original_dir)

                return True, None

        except Exception as e:
            # Clean up on error
            try:
                back_to_master_branch(repo_path)
            except Exception as cleanup_error:
                tab_print(f"Error during cleanup: {str(cleanup_error)}")

            # Return to original directory
            os.chdir(original_dir)

            # Log detailed error to the PR with signature
            error_msg = f"Failed to process PR# {pr_number} comment: {str(e)}\n\n```\n{traceback.format_exc()}\n```"
            tab_print(f"Error logged to PR: {error_msg}")
            raise Exception(error_msg)
    else:
        # Handle case where there are no user comments
        pr_msg = f"No user feedback found to process on the PR #{pr_number}"
        tab_print(pr_msg)
        return False, pr_msg


def standalone_pr_flow(
        issue_or_pr: Union[Issue, PullRequest],
        repo_name: str,
) -> Tuple[bool, Optional[str]]:

    try:
        # Get repo object and pull request
        client = get_github_client()
        repo = get_repository(client, repo_name)
        pr_obj = repo.get_pull(issue_or_pr.number)
        branch_name = get_pr_branch(pr_obj)
        repo_path = bot_tools.get_local_repo_path(repo_name)

        original_dir = os.getcwd()
        os.chdir(repo_path)
        checkout_branch(repo_path, branch_name, create=False)

        summarized_comments, comment_list, summary_comment_str = summarize_relevant_comments(
            issue_or_pr, repo_name)
        if summary_comment_str == '':
            summary_comment_str = 'No relevant comments found'

        # First generate edit command from previous discussion
        response, _ = generate_edit_command_response(
            issue_or_pr, repo_name, summary_comment_str)

        try:
            # Run aider with the generated command
            aider_output = run_aider(response, repo_path)

            # Push changes with authentication
            push_changes_with_authentication(
                repo_path,
                issue_or_pr,
                branch_name
            )

            # write_issue_response(issue, "Generated edit command:\n" + response)
            write_str = f"Generated edit command:\n---\n{response}\n\n" + \
                f"Aider output:\n<details><summary>View Aider Output</summary>\n\n```{aider_output}```\n</details>"
            write_pr_comment(
                pr_obj,
                write_str,
                aider_output=aider_output,
                llm_config=llm_config,
                write_str=write_str
            )

            # Switch back to main branch
            back_to_master_branch(repo_path)
            # Return to original directory
            os.chdir(original_dir)

        except Exception as e:
            # Clean up on error
            try:
                back_to_master_branch(repo_path)
            except Exception as cleanup_error:
                tab_print(f"Error during cleanup: {str(cleanup_error)}")

            # Return to original directory
            os.chdir(original_dir)

            # Log detailed error to the PR with signature
            error_msg = f"Failed to process standalone PR flow: {str(e)}\n\n```\n{traceback.format_exc()}\n```"
            tab_print(f"Error logged to PR: {error_msg}")
            raise Exception(error_msg)

        return True, None

    except Exception as e:
        # Handle errors in the initial setup
        error_msg = f"Failed to initialize standalone PR flow: {str(e)}\n\n```\n{traceback.format_exc()}\n```"
        tab_print(f"Error logged to PR: {error_msg}")
        raise Exception(error_msg)


def process_issue(
    issue_or_pr: Union[Issue, PullRequest],
    repo_name: str,
) -> Tuple[bool, Optional[str]]:
    """
    Process a single issue or PR - check if it needs response and generate one

    Args:
        issue_or_pr: The GitHub issue or PR to process

    Returns:
        Tuple of (whether response was posted, optional error message)
    """
    is_pr = is_pull_request(issue_or_pr)
    entity_type = "PR" if is_pr else "issue"
    print(f"Processing {entity_type} #{issue_or_pr.number}")

    try:
        has_bot_mention = triggers.has_blech_bot_tag(issue_or_pr) \
            or '[ blech_bot ]' in (issue_or_pr.title or '').lower()
        if not has_bot_mention:
            # This is a skip outcome, not an error
            return False, f"{entity_type} #{issue_or_pr.number} does not have blech_bot label"

        # Check if a pr_creation comment exists for the issue
        pr_creation_comment_bool, pr_creation_comment = triggers.has_pr_creation_comment(
            issue_or_pr)
        # Check if already responded without user feedback
        already_responded = triggers.has_bot_response(
            issue_or_pr) and not triggers.has_user_feedback(issue_or_pr)
        if already_responded and not pr_creation_comment_bool:
            # This is a skip outcome, not an error
            return False, f"{entity_type} already has a bot response without feedback from user"

        has_error = triggers.has_error_comment(issue_or_pr)

        # Skip processing if an error has been reported
        if has_error:
            return False, f"Error reported in {entity_type} #{issue_or_pr.number}. Skipping further processing."

        # Handle PR differently
        if is_pr:
            tab_print('Detected as a Pull Request (PR)')
            tab_print('Processing standalone PR flow')

            result, err_msg = standalone_pr_flow(
                issue_or_pr,
                repo_name
            )
            return result, err_msg

        else:  # It's an issue

            # Process PR Already created from issue
            # If PR has been created, respond if it has an unresponded comment
            if pr_creation_comment_bool and not has_error:
                # respond_pr_comment_flow checks for unresolved comments on PR
                tab_print('Checking for comments on PR generated by this issue')
                result, err_msg = respond_pr_comment_flow(
                    issue_or_pr,
                    repo_name,
                    pr_creation_comment
                )
                return result, err_msg

            # Developing pull request from issue
            # Check for develop_issue trigger next
            elif triggers.has_develop_issue_trigger(issue_or_pr):
                result, err_msg = develop_issue_flow(
                    issue_or_pr,
                    repo_name,
                    is_pr=is_pr
                )
                return result, err_msg

            # Process as new issue
            else:
                # Generate and post response
                trigger = check_triggers(issue_or_pr)
                response_func = response_selector(trigger)
                if response_func is None:
                    # This is a skip outcome, not an error
                    return False, f"No trigger found for {entity_type} #{issue_or_pr.number}"
                response, all_content = response_func(issue_or_pr, repo_name)
                write_issue_response(issue_or_pr, response)
                return True, None
    except Exception as e:
        # This is a true error outcome
        error_msg = f"Error processing {entity_type} #{issue_or_pr.number}: {str(e)}\n\n```\n{traceback.format_exc()}\n```"
        # Log the error to the issue/PR with signature
        write_issue_response(issue_or_pr, add_signature_to_comment(
            error_msg, llm_config['model']))
        tab_print(f"Error logged to {entity_type}: {error_msg}")
        return False, f"ERROR: {error_msg}"


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

        # Current commit
        current_commit = git.Repo(repo_path).head.object.hexsha

        # Run aider with the message
        result = subprocess.run(
            ['aider', '--sonnet', '--yes-always', '--message', message],
            check=True,
            capture_output=True,
            text=True
        )
        if 'Re-run aider to use new version' in result.stdout:
            result = subprocess.run(
                ['aider', '--sonnet', '--yes-always', '--message', message],
                check=True,
                capture_output=True,
                text=True
            )

        # Check if there are any changes
        updated_commit = git.Repo(repo_path).head.object.hexsha
        if current_commit == updated_commit:
            raise RuntimeError("No changes made by Aider")

        # Return to original directory
        os.chdir(original_dir)

        return result.stdout

    except FileNotFoundError:
        error_msg = "Aider not found. Please install it first with 'pip install aider-chat'"
        os.chdir(original_dir) if 'original_dir' in locals() else None
        raise ValueError(error_msg)
    except subprocess.CalledProcessError as e:
        error_msg = f"Failed to run aider: {e.stderr}"
        os.chdir(original_dir) if 'original_dir' in locals() else None
        raise RuntimeError(error_msg)
    except Exception as e:
        error_msg = f"Unexpected error running aider: {str(e)}\n\n```\n{traceback.format_exc()}\n```"
        os.chdir(original_dir) if 'original_dir' in locals() else None
        raise RuntimeError(error_msg)


def process_repository(
    repo_name: str,
) -> None:
    """
    Process all open issues and PRs in a repository

    Args:
        repo_name: Full name of repository (owner/repo)
    """
    try:
        # Initialize GitHub client
        client = get_github_client()
        repo = get_repository(client, repo_name)

        # Get local repository path
        repo_dir = bot_tools.get_local_repo_path(repo_name)

        # Clone repository only if not already present
        if not os.path.exists(repo_dir):
            repo_dir = clone_repository(repo)

        # Determine the default branch
        default_branch = repo.default_branch

        # Ensure repository is on the default branch
        try:
            checkout_branch(repo_dir, default_branch)
        except Exception as e:
            error_msg = f"Error switching to default branch '{default_branch}': {str(e)}\n\n```\n{traceback.format_exc()}\n```"
            tab_print(error_msg)
            # We can't log this to an issue since we're processing the whole repository
            # But we'll print it for logging purposes
            return

        # Update repository
        update_repository(repo_dir)

        # Get open issues
        open_issues = repo.get_issues(state='open')

        # Process each issue and PR
        for item in open_issues:
            entity_type = "PR" if is_pull_request(item) else "issue"

            # Process the issue/PR and determine the outcome
            success, message = process_issue(item, repo_name)
            if success:
                # Success outcome
                tab_print(
                    f"Successfully processed {entity_type} #{item.number}")
            else:
                # Determine if this is a skip or error outcome based on message content
                if "ERROR" in message:
                    # This is an error outcome
                    tab_print(
                        f"ERROR processing {entity_type} #{item.number}: {message}")
                else:
                    # This is a skip outcome
                    tab_print(
                        f"Skipped {entity_type} #{item.number}: {message}")

    except Exception as e:
        error_msg = f"Error processing repository {repo_name}: {str(e)}\n\n```\n{traceback.format_exc()}\n```"
        tab_print(error_msg)


def initialize_bot() -> None:
    """
    Initialize the bot and ensure it is up-to-date.
    """
    if params['auto_update']:
        print('===============================')
        print("== Updating bot repository...")
        # Path to the bot's own repository
        self_repo_path = os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))

        # Update the bot's own repository
        from git_utils import update_self_repo
        print(f"Updating bot repository at {self_repo_path}")
        update_performed = update_self_repo(self_repo_path)
        if update_performed:
            print("Bot repository update complete")
            print("Exiting to apply updates. Please restart the bot.")
            print('===============================')
            os._exit(0)  # Terminate process to allow restart with updates
        else:
            print("Bot already up to date")
            print('===============================')
    else:
        print('===============================')
        print("Auto-update is disabled. Skipping bot repository update.")
        print('===============================')

    if not params['print_llm_output']:
        print('===============================')
        print("LLM output printing is disabled. Set 'print_llm_output' to true in the parameters to enable.")
        print('===============================')


if __name__ == '__main__':
    # Initialize the bot (self-update)
    initialize_bot()

    # Get list of repositories to process
    tracked_repos = get_tracked_repos()
    print(f'Found {len(tracked_repos)} tracked repositories')
    pprint(tracked_repos)

    # Process each repository
    for repo_name in tracked_repos:
        print(f'\n=== Processing repository: {repo_name} ===')
        try:
            process_repository(repo_name)
            print(f'Completed processing {repo_name}')
        except Exception as e:
            tab_print(f'Error processing {repo_name}: {str(e)}')
            continue

    print('\nCompleted processing all repositories')
