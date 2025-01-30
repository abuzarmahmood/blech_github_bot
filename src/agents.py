"""
Agent creation and configuration for the GitHub bot
"""
import os
import autogen
from autogen import ConversableAgent, AssistantAgent
import bot_tools
from git_utils import get_issue_comments
from github.Issue import Issue
import random

# Get callable tool functions
tool_funcs = []
for func in dir(bot_tools):
    if callable(getattr(bot_tools, func)):
        tool_funcs.append(eval(f'bot_tools.{func}'))


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
        },
    )

    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OpenAI API key not found in environment variables")

    llm_config = {
        "model": "gpt-4o",
        "api_key": api_key,
        "temperature": random.uniform(0, 0.05),
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

    return user, file_assistant, edit_assistant


def create_summary_agent(llm_config: dict) -> AssistantAgent:
    """Create and configure the summary agent

    Args:
        llm_config: Configuration for the LLM

    Returns:
        Configured summary assistant agent
    """
    summary_assistant = AssistantAgent(
        name="summary_assistant",
        llm_config=llm_config,
        system_message="""You are a helpful GitHub bot that reviews issues and generates appropriate responses.
        Analyze the issue details carefully and summarize the suggestions and changes made by other agents.
        """,
    )

    return summary_assistant


def get_file_analysis_prompt(
        repo_name: str,
        repo_path: str,
        details: dict,
        issue: Issue
) -> str:
    """Generate prompt for file analysis agent

    Args:
        repo_name: Name of repository
        repo_path: Path to repository
        details: Dictionary of issue details
        issue: Issue object

    Returns:
        Formatted prompt string
    """
    comments_objs = get_issue_comments(issue)
    all_comments = [c.body for c in comments_objs]
    if len(all_comments) == 0:
        last_comment_str = ""
        comments_str = ""
    elif len(all_comments) == 1:
        last_comment_str = f"Last comment: {all_comments[0]}"
        comments_str = ""
    else:
        comments = "\n".join([c.body for c in comments_objs[:-1]])
        last_comment_str = f"Last comment: {comments_objs[-1].body}"
        comments_str = f"Also think of these comments as part of the response context:\n    {comments}"

    return f"""Please analyze this GitHub issue and suggest files that need to be modified to address the issue.

Repository: {repo_name}
Local path: {repo_path}
Title: {details['title']}
Body: {details['body']}
{last_comment_str}

Generate a helpful and specific response addressing the issue contents.
Use the tools you have. Do not ask for user input or expect it.
To find details of files use read_merged_summary or read_merged_docstrings
If those are not functioning, use tools like search_for_file to search for .py files, or other tools you have.

Return response in format:
    - File: path/to/file1.py
    - Description: Brief description of function of file1

    - File: path/to/file2.py
    - Description: Brief description of function of file2

{comments_str}

Reply "TERMINATE" in the end when everything is done.
"""


def get_edit_suggestion_prompt(
        repo_name: str,
        repo_path: str,
        details: dict,
        issue: Issue,
) -> str:
    """Generate prompt for edit suggestion agent

    Args:
        repo_name: Name of repository
        repo_path: Path to repository
        details: Dictionary of issue details

    Returns:
        Formatted prompt string
    """
    comments_objs = get_issue_comments(issue)
    all_comments = [c.body for c in comments_objs]
    if len(all_comments) == 0:
        last_comment_str = ""
        comments_str = ""
    elif len(all_comments) == 1:
        last_comment_str = f"Last comment: {all_comments[0]}"
        comments_str = ""
    else:
        comments = "\n".join([c.body for c in comments_objs[:-1]])
        last_comment_str = f"Last comment: {comments_objs[-1].body}"
        comments_str = f"Also think of these comments as part of the response context:\n    {comments}"

    return f"""Suggest what changes can be made to resolve this issue:
Repository: {repo_name}
Local path: {repo_path}
Issue Title: {details['title']}
Issue Body: {details['body']}
{last_comment_str}

{comments_str}


Use the tools you have. Do not ask for user input or expect it.
Do not look for files again. Use the files suggested by the previous agent.
Provide code blocks which will address the issue where you can and suggest specific lines in specific files where changes can be made.
Try to read the whole file to understand context where possible. If file is too large, search for specific functions or classes. If you can't find functions to classes, try reading sets of lines repeatedly.
Reply "TERMINATE" in the end when everything is done."""


def get_generate_edit_command_prompt(repo_name: str, repo_path: str, details: dict, issue: Issue) -> str:
    """Generate prompt for generate_edit_command agent

    Args:
        repo_name: Name of repository
        repo_path: Path to repository
        details: Dictionary of issue details
        issue: Issue object

    Returns:
        Formatted prompt string
    """
    comments_objs = get_issue_comments(issue)
    all_comments = [c.body for c in comments_objs]
    if len(all_comments) == 0:
        last_comment_str = ""
        comments_str = ""
    elif len(all_comments) == 1:
        last_comment_str = f"Last comment: {all_comments[0]}"
        comments_str = ""
    else:
        comments = "\n".join([c.body for c in comments_objs[:-1]])
        last_comment_str = f"Last comment: {comments_objs[-1].body}"
        comments_str = f"Also think of these comments as part of the response context:\n    {comments}"

    return f"""Please analyze this GitHub issue and generate a detailed edit command:

Repository: {repo_name}
Local path: {repo_path}
Title: {details['title']}
Body: {details['body']}
{last_comment_str}

Generate a specific and detailed edit command that captures all the changes needed.
Include file paths, line numbers, and exact code changes where possible.
Format the command in a way that can be parsed by automated tools.

{comments_str}

Reply "TERMINATE" in the end when everything is done.
"""


def get_feedback_prompt(repo_name: str, repo_path: str, original_response: str, feedback_text: str, max_turns: int) -> str:
    """Generate prompt for feedback processing

    Args:
        repo_name: Name of repository
        repo_path: Path to repository
        original_response: Original bot response
        feedback_text: User feedback text
        max_turns: Maximum conversation turns

    Returns:
        Formatted prompt string
    """
    return f"""Process this user feedback on the previous bot response and generate an improved response:
Repository: {repo_name}
Local path: {repo_path}

Use the tools you have. Do not ask for user input or expect it.
DO NOT SUGGEST CODE EXECUTIONS. Only make code editing suggestions.
To find details of files use read_merged_summary or read_merged_docstrings
If those are not functioning, use tools like search_for_file to search for .py files, or other tools you have.
Read relevant files to understand context where possible. If file is too large, search for specific functions or classes. If you can't find functions to classes, try reading sets of lines repeatedly.
Finish the job by suggesting specific lines in specific files where changes can be made.
You have {max_turns} turns to complete this task.

Previous Response:
{original_response}

User Feedback:
{feedback_text}

Please generate an updated response that addresses the feedback while maintaining any useful information from the original response.
Reply "TERMINATE" when done.
"""


def create_feedback_agent(llm_config: dict) -> AssistantAgent:
    """Create and configure the feedback processing agent

    Args:
        llm_config: Configuration for the LLM

    Returns:
        Configured feedback assistant agent
    """
    feedback_assistant = AssistantAgent(
        name="feedback_assistant",
        llm_config=llm_config,
        system_message="""You are a helpful GitHub bot that processes user feedback on previous bot responses.
        Analyze the user's feedback carefully and suggest improvements to the original response.
        Focus on addressing specific concerns raised by the user.
        Maintain a professional and helpful tone.
        DO NOT MAKE ANY CHANGES TO THE FILES OR CREATE NEW FILES. Only provide information or suggestions.
        If no changes are needed, respond accordingly.
        NEVER ask for user input and NEVER expect it.
        If possible, suggest concrete code changes or additions that can be made. Be specific about what files and what lines.
        Provide code blocks where you can.
        Include any relevant code snippets or technical details from the original response that should be preserved.
        """,
    )

    for this_func in tool_funcs:
        feedback_assistant.register_for_llm(
            name=this_func.__name__,
            description=this_func.__doc__,
        )(this_func)

    return feedback_assistant


def create_generate_edit_command_agent(llm_config: dict) -> AssistantAgent:
    """Create and configure the generate_edit_command agent

    Args:
        llm_config: Configuration for the LLM

    Returns:
        Configured generate_edit_command assistant agent
    """
    generate_edit_command_assistant = AssistantAgent(
        name="generate_edit_command_assistant",
        llm_config=llm_config,
        system_message="""You are a helpful GitHub bot that synthesizes all discussion in an issue thread to generate a command for a bot to make edits.
        Analyze the issue details and comments carefully to generate a detailed and well-organized command.
        Ensure the command provides enough information for the downstream bot to make changes accurately.
        NEVER ask for user input and NEVER expect it.
        Provide code blocks where you can.
        Reply "TERMINATE" in the end when everything is done.
        """,
    )

    for this_func in tool_funcs:
        generate_edit_command_assistant.register_for_llm(
            name=this_func.__name__,
            description=this_func.__doc__,
        )(this_func)

    return generate_edit_command_assistant
