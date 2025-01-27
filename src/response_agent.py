"""
Agent for generating responses to GitHub issues using pyautogen
"""
from pprint import pprint
import json
from typing import Optional, Tuple
import os
import autogen
from autogen import ConversableAgent, AssistantAgent
from github.Issue import Issue
from github.Repository import Repository
from git_utils import (
    get_github_client,
    get_repository,
    has_bot_response,
    has_blech_bot_tag,
    write_issue_response,
    get_issue_details,
    clone_repository,
    update_repository
)

import bot_tools
# tool_funcs = [func for func in dir(bot_tools) if callable(getattr(bot_tools, func))]
tool_funcs = []
for func in dir(bot_tools):
    if callable(getattr(bot_tools, func)):
        tool_funcs.append(eval(f'bot_tools.{func}'))

# # Output results to json
# with open('chat_results.txt', 'w') as f:
#     pprint(chat_results, stream=f)


def create_agents():
    """Create and configure the autogen agents"""

    user = autogen.UserProxyAgent(
        name="User",
        human_input_mode="NEVER",
        is_termination_msg=lambda x: x.get("content", "") and x.get(
            "content", "").rstrip().endswith("TERMINATE"),
        code_execution_config={
            "last_n_messages": 1,
            "work_dir": "tasks",
            "use_docker": False,
        },  # Please set use_docker=True if docker is available to run the generated code. Using docker is safer than running the generated code directly.
    )

    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OpenAI API key not found in environment variables")

    llm_config = {
        "model": "gpt-4o",
        "api_key": api_key,
        "temperature": 0
    }

    # Create assistant agent for generating responses
    file_assistant = AssistantAgent(
        name="file_assistant",
        llm_config=llm_config,
        system_message="""You are a helpful GitHub bot that reviews issues and generates appropriate responses.
        Analyze the issue details carefully check which files (if any) need to be modified.
        If not files are given by user, use the tools you have to find and suggest the files that need to be modified.
        DO NOT MAKE ANY CHANGES TO THE FILES OR CREATE NEW FILES. Only provide information or suggestions.
        NEVER ask for user input and NEVER expect it.
        Return file names that are relevant, and if possible, specific lines where changes can be made.
        Instead of listing the whole dir, use read_merged_summary or read_merged_docstrings
        Reply "TERMINATE" in the end when everything is done.
        """,
    )

    edit_assistant = AssistantAgent(
        name="edit_assistant",
        llm_config=llm_config,
        system_message="""You are a helpful GitHub bot that reviews issues and generates appropriate responses.
        Analyze the issue details carefully and suggest the changes that need to be made.
        Use to tools available to you to gather information and suggest the necessary changes.
        DO NOT MAKE ANY CHANGES TO THE FILES OR CREATE NEW FILES. Only provide information or suggestions.
        If no changes are needed, respond accordingly.
        NEVER ask for user input and NEVER expect it.
        If possible, suggest concrete code changes or additions that can be made. Be specific about what files and what lines.
        Provide code blocks where you can.
        Reply "TERMINATE" in the end when everything is done.
        """,
    )

    for this_func in tool_funcs:
        file_assistant.register_for_llm(
            name=this_func.__name__,
            description=this_func.__doc__,
        )(this_func)
        edit_assistant.register_for_llm(
            name=this_func.__name__,
            description=this_func.__doc__,
        )(this_func)
        user.register_for_execution(
            name=this_func.__name__)(this_func)

    # Summarize results using reflection_with_llm
    summary_assistant = AssistantAgent(
        name="summary_assistant",
        llm_config=llm_config,
        system_message="""You are a helpful GitHub bot that reviews issues and generates appropriate responses.
        Analyze the issue details carefully and summarize the suggestions and changes made by other agents.
        """,
    )

    feedback_assistant = AssistantAgent(
        name="feedback_assistant",
        llm_config=llm_config,
        system_message="""You are a helpful GitHub bot that processes user feedback on previous bot responses.
        Analyze the user's feedback carefully and suggest improvements to the original response.
        Focus on addressing specific concerns raised by the user.
        Maintain a professional and helpful tone.
        Include any relevant code snippets or technical details from the original response that should be preserved.
        """,
    )

    for this_func in tool_funcs:
        feedback_assistant.register_for_llm(
            name=this_func.__name__,
            description=this_func.__doc__,
        )(this_func)

    return user, file_assistant, edit_assistant, summary_assistant, feedback_assistant


def generate_issue_response(
        issue: Issue,
        repo_name: str,
        feedback_text: str = None,
) -> str:
    """
    Generate an appropriate response for a GitHub issue using autogen agents

    Args:
        issue: The GitHub issue to respond to
        repo_name: Full name of repository (owner/repo)

    Returns:
        Generated response text
    """
    # Get path to repository
    repo_path = bot_tools.get_local_repo_path(repo_name)

    # Get issue details
    details = get_issue_details(issue)

    # Create agents
    user, file_assistant, edit_assistant, summary_assistant = create_agents()

    # Construct prompt with issue details
    prompt = f"""Please analyze this GitHub issue and suggest files that need to be modified to address the issue.

Repository: {repo_name}
Local path: {repo_path}
Title: {details['title']}
Body: {details['body']}
Labels: {', '.join(details['labels'])}
Assignees: {', '.join(details['assignees'])}

Generate a helpful and specific response addressing the issue contents.
Use the tools you have. Do not ask for user input or expect it.
To find details of files use read_merged_summary or read_merged_docstrings
If those are not functioning, use tools like search_for_file to search for .py files, or other tools you have.

Return response in format:
    - File: path/to/file1.py
    - Description: Brief description of function of file1

    - File: path/to/file2.py
    - Description: Brief description of function of file2

Reply "TERMINATE" in the end when everything is done.
"""

    edit_assistant_prompt = f"""Suggest what changes can be made to resolve this issue:
Repository: {repo_name}
Local path: {repo_path}
Issue Title: {details['title']}
Issue Body: {details['body']}
Use the tools you have. Do not ask for user input or expect it.
Do not look for files again. Use the files suggested by the previous agent.
Provide code blocks which will address the issue where you can and suggest specific lines in specific files where changes can be made.
Try to read the whole file to understand context where possible. If file is too large, search for specific functions or classes. If you can't find functions to classes, try reading sets of lines repeatedly.
Reply "TERMINATE" in the end when everything is done."""

    # Extract response from chat history
    chat_results = user.initiate_chats(
        [
            {
                "recipient": file_assistant,
                "message": prompt,
                "max_turns": 10,
                # "summary_method": "reflection_with_llm",
                "summary_method": "last_msg",
            },
            {
                "recipient": edit_assistant,
                "message": edit_assistant_prompt,
                "max_turns": 10,
                "summary_method": "reflection_with_llm",
            },
        ]
    )

    # Grab everything but tool calls
    results_to_summarize = [
        [
            x for x in this_result.chat_history if 'tool_call' not in str(x)
        ]
        for this_result in chat_results
    ]

    if any([len(x) == 0 for x in results_to_summarize]):
        raise ValueError(
            "Something went wrong with collecting results to summarize")

    summary_results = summary_assistant.initiate_chats(
        [
            {
                "recipient": summary_assistant,
                "message": f"Summarize the suggestions and changes made by the other agents. Repeat any code snippets as is.\n\n{results_to_summarize}",
                "silent": False,
                "max_turns": 1,
            },
        ]
    )

    response = summary_results[0].chat_history[-1]['content']
    all_content = results_to_summarize + [response]

    # If there's feedback, process it
    if feedback_text:
        feedback_prompt = f"""Process this user feedback on the previous bot response and generate an improved response:

Previous Response:
{response}

User Feedback:
{feedback_text}

Please generate an updated response that addresses the feedback while maintaining any useful information from the original response.
Reply "TERMINATE" when done.
"""
        
        feedback_results = user.initiate_chats(
            [
                {
                    "recipient": feedback_assistant,
                    "message": feedback_prompt,
                    "max_turns": 5,
                    "summary_method": "last_msg",
                }
            ]
        )
        
        updated_response = feedback_results[0].chat_history[-1]['content']
        all_content.extend([feedback_text, updated_response])
        return updated_response, all_content

    return response, all_content


def process_issue(
    issue: Issue,
    repo_name: str,
    ignore_checks: bool = False,
    feedback_text: str = None,
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

        # Check if already responded
        if has_bot_response(issue) and not ignore_checks:
            return False, "Issue already has bot response"

        # Generate and post response
        response, all_content = generate_issue_response(issue, repo_name, feedback_text)
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
    repo_name = tracked_repos[1]
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

    success_list = []
    max_success = 10
    for issue in open_issues[:1]:
        if len(success_list) > max_success:
            print(f"Reached max success limit of {max_success}")
            break

        bot_bool = not has_bot_response(issue)
        # comment_bool = issue.comments == 0
        found_branches = [
            branch for branch in branches if branch_checker(branch, issue)]

        if len(found_branches) == 0:
            branch_bool = True
        else:
            branch_bool = False
            print(f"Branch found for issue {issue.number} = {found_branches}")

        pr_bool = issue.pull_request is None

        fin_bool = bot_bool and branch_bool and pr_bool

        if fin_bool:
            success, error = process_issue(
                issue, repo_name, ignore_checks=True)
            if success:
                print(f"Successfully processed issue #{issue.number}")
                success_list.append(issue.number)
            else:
                print(f"Skipped issue #{issue.number}: {error}")
