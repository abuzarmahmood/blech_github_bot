"""
Agent for generating responses to GitHub issues using pyautogen
"""
from typing import Optional, Tuple, List

from dotenv import load_dotenv
import string
import triggers
from agents import (
    create_user_agent,
    create_agent,
    generate_prompt,
    parse_comments
)
from urlextract import URLExtract
import agents
from autogen import AssistantAgent
import bot_tools

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
    push_changes_with_authentication,
)
from github.Repository import Repository
from github.Issue import Issue
from branch_handler import (
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

load_dotenv()
src_dir = os.path.dirname(os.path.abspath(__file__))
base_dir = os.path.dirname(src_dir)

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


def scrape_text_from_url(url: str) -> str:
    """Scrape text content from a given URL.

    Args:
        url: The URL to scrape text from.

    Returns:
        The scraped text content.
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # Raise an error for bad responses
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
        print(f"Error fetching URL {url}: {e}")
        return f"Error fetching URL {url}: {str(e)}"


def summarize_text(text: str, max_length: int = 1000) -> str:
    """Summarize text to a maximum length.

    Args:
        text: The text to summarize.
        max_length: Maximum length of the summary.

    Returns:
        The summarized text.
    """
    if len(text) <= max_length:
        return text

    # Simple truncation with ellipsis for now
    return text[:max_length] + "...\n[Text truncated due to length]"


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

        comment_summary_results = comment_summary_assistant.initiate_chat(
            comment_summary_assistant,
            message=summary_prompt,
            max_turns=1,
        )

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

    # Extract URLs from issue and scrape content
    urls = extract_urls_from_issue(issue)
    url_contents = {}

    if urls:
        print(f"Found {len(urls)} URLs in issue")
        for url in urls:
            print(f"Scraping content from {url}")
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

    for this_chat in feedback_results[0].chat_history[::-1]:
        this_content = this_chat['content']
        if check_not_empty(this_content):
            updated_response = this_content
            break
    all_content = [original_response, feedback_text, updated_response]
    signature = f"\n\n---\n*This response was automatically generated by blech_bot using model {llm_config['model']}*"
    return updated_response + signature, all_content


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

    # Extract URLs from issue and scrape content
    urls = extract_urls_from_issue(issue)
    url_contents = {}

    if urls:
        print(f"Found {len(urls)} URLs in issue")
        for url in urls:
            print(f"Scraping content from {url}")
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
    )

    response = summary_results.chat_history[-1]['content']
    all_content = results_to_summarize + [response]

    signature = f"\n\n---\n*This response was automatically generated by blech_bot using model {llm_config['model']}*"
    return response + signature, all_content


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
    print('===============================')
    print('Generating edit command response')
    print('===============================')

    # Get path to repository and issue details
    repo_path = bot_tools.get_local_repo_path(repo_name)
    details = get_issue_details(issue)

    # Extract URLs from issue and scrape content
    urls = extract_urls_from_issue(issue)
    url_contents = {}

    if urls:
        print(f"Found {len(urls)} URLs in issue")
        for url in urls:
            print(f"Scraping content from {url}")
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

    # response = chat_results[0].chat_history[-1]['content']
    for this_chat in chat_results[0].chat_history[::-1]:
        this_content = this_chat['content']
        if check_not_empty(this_content):
            response = this_content
            break
    all_content = [response]
    signature = f"\n\n---\n*This response was automatically generated by blech_bot using model {llm_config['model']}*"
    return response + signature, all_content

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
        print('Triggered by generate_edit_command')
        return "generate_edit_command"
    elif triggers.has_user_feedback(issue):
        print('Triggered by user feedback')
        return "feedback"
    elif not triggers.has_bot_response(issue):
        print('Triggered by new issue')
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


def process_issue(
    issue: Issue,
    repo_name: str,
) -> Tuple[bool, Optional[str]]:
    """
    Process a single issue - check if it needs response and generate one

    Args:
        issue: The GitHub issue to process

    Returns:
        Tuple of (whether response was posted, optional error message)
    """
    print(f"Processing issue #{issue.number}")
    try:
        # Check if issue has blech_bot tag or blech_bot in title, and no existing response
        has_bot_mention = triggers.has_blech_bot_tag(
            issue) or "[ blech_bot ]" in issue.title.lower()
        if not has_bot_mention:
            return False, "Issue does not have blech_bot tag or mention in title"
        already_responded = triggers.has_bot_response(
            issue) and not triggers.has_user_feedback(issue)
        pr_comment_bool, pr_comment = triggers.has_pr_creation_comment(issue)
        if already_responded and not pr_comment_bool:
            return False, "Issue already has a bot response without feedback from user"

        # Check for user comments on PR first
        if pr_comment_bool:

            repo_path = bot_tools.get_local_repo_path(repo_name)
            repo = get_repository(get_github_client(), repo_name)

            # Get latest user comment
            extractor = URLExtract()
            urls = extractor.find_urls(pr_comment)[0]
            pr_number = int(urls.split('/')[-1])
            pr = repo.get_pull(pr_number)

            comments = list(pr.get_issue_comments())
            # find the latest bot comment
            latest_bot_idx = -1
            for i, comment in enumerate(comments):
                if "generated by blech_bot" in comment.body:
                    latest_bot_idx = i

            # check if there are any comments after the latest bot comment
            user_feedback_bool = latest_bot_idx >= 0 and latest_bot_idx < len(
                comments) - 1

            branch_name = get_development_branch(
                issue, repo_path, create=False)

            # Only run if branch exists and user comment is found on PR
            if branch_name and user_feedback_bool:
                user_comment = comments[-1].body
                print('Triggered by user comment on PR')

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
                            issue, repo_name)

                        if summary_comment_str == '':
                            summary_comment_str = 'No relevant comments found'

                        # Pass to generate_edit_command agent first
                        response, _ = generate_edit_command_response(
                            issue, repo_name, summary_comment_str)

                        # Then run aider with the generated command
                        aider_output = run_aider(response, repo_path)

                        # Push changes
                        push_success, err_msg = push_changes_with_authentication(
                            repo_path,
                            pr,
                            branch_name)

                        if not push_success:
                            return False, f"Failed to push changes: {err_msg}"

                        # Write response
                        write_str = f"Applied changes based on comment:\n<details><summary>View Aider Output</summary>\n\n```\n{aider_output}\n```\n</details>"
                        signature = f"\n\n---\n*This response was automatically generated by blech_bot using model {llm_config['model']}*"
                        pr.create_issue_comment(write_str+signature)

                        # Clean up
                        back_to_master_branch(repo_path)

                        # Return to original directory
                        os.chdir(original_dir)

                        return True, None

                except Exception as e:
                    # Clean up on error
                    back_to_master_branch(repo_path)
                    # Return to original directory
                    os.chdir(original_dir)
                    raise RuntimeError(
                        f"Failed to process PR comment: {str(e)}")

        # Check for develop_issue trigger next
        elif triggers.has_develop_issue_trigger(issue):
            print('Triggered by [ develop_issue ] command')
            repo_path = bot_tools.get_local_repo_path(repo_name)

            # Check for existing branches
            branch_name = get_development_branch(
                issue, repo_path, create=False)
            # if branch_name is not None:
            #     return False, f"Branch {branch_name} already exists for issue #{issue.number}"

            # Check for linked PRs
            if has_linked_pr(issue):
                return False, f"Issue #{issue.number} already has a linked pull request"

            # Check if issue has label "under_development"
            if "under_development" in [label.name for label in issue.labels]:
                return False, f"Issue #{issue.number} is already under development"

            # First generate edit command from previous discussion
            response, _ = generate_edit_command_response(issue, repo_name)

            branch_name = get_development_branch(issue, repo_path, create=True)
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
                push_success, err_msg = push_changes_with_authentication(
                    repo_path,
                    issue,
                    branch_name
                )

                pr_url = create_pull_request_from_issue(issue, repo_path)
                pr_number = pr_url.split('/')[-1]
                pull = repo.get_pull(int(pr_number))

                # Create pull request
                write_issue_response(
                    issue,
                    f"Created pull request: {pr_url}\nContinue discussion there."
                )

                # Mark issue with label "under_development"
                issue.add_to_labels("under_development")

                if not push_success:
                    return False, f"Failed to push changes: {err_msg}"

                # write_issue_response(issue, "Generated edit command:\n" + response)
                write_str = f"Generated edit command:\n---\n{response}\n\n" + \
                    f"Aider output:\n<details><summary>View Aider Output</summary>\n\n```{aider_output}```\n</details>"
                signature = f"\n\n---\n*This response was automatically generated by blech_bot using model {llm_config['model']}*"
                full_response = write_str + signature
                pull.create_issue_comment(full_response)

                # Switch back to main branch
                back_to_master_branch(repo_path)
                # Return to original directory
                os.chdir(original_dir)

            except Exception as e:
                # Clean up on error
                back_to_master_branch(repo_path)
                delete_branch(repo_path, branch_name, force=True)
                # Return to original directory
                os.chdir(original_dir)
                raise RuntimeError(
                    f"Failed to process develop issue: {str(e)}")

            return True, None

        # Generate and post response
        trigger = check_triggers(issue)
        response_func = response_selector(trigger)
        if response_func is None:
            return False, f"No trigger found for issue #{issue.number}"
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
        print(
            f"Error switching to default branch '{default_branch}': {str(e)}")
        return
    # Update repository
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
            print(f'Error processing {repo_name}: {str(e)}')
            continue

    print('\nCompleted processing all repositories')
