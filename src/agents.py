"""
Agent creation and configuration for the GitHub bot
"""
import os
import autogen
import subprocess
from autogen import ConversableAgent, AssistantAgent, UserProxyAgent
import bot_tools
from git_utils import get_issue_comments
from github.Issue import Issue
import random


# Get callable tool functions
tool_funcs = []
for func in dir(bot_tools):
    if callable(getattr(bot_tools, func)):
        tool_funcs.append(eval(f'bot_tools.{func}'))


agent_system_messages = {
    "file_assistant": """You are a helpful GitHub bot that reviews issues and generates appropriate responses.
        Analyze the issue details carefully check which files (if any) need to be modified.
        If not files are given by user, use the tools you have to find and suggest the files that need to be modified.
        DO NOT MAKE ANY CHANGES TO THE FILES OR CREATE NEW FILES. Only provide information or suggestions.
        NEVER ask for user input and NEVER expect it.
        Return file names that are relevant, and if possible, specific lines where changes can be made.
        Instead of listing the whole dir, use read_merged_summary or read_merged_docstrings
        Reply "TERMINATE" in the end when everything is done.
        """,
    "edit_assistant": """You are a helpful GitHub bot that reviews issues and generates appropriate responses.
        Analyze the issue details carefully and suggest the changes that need to be made.
        Use to tools available to you to gather information and suggest the necessary changes.
        DO NOT MAKE ANY CHANGES TO THE FILES OR CREATE NEW FILES. Only provide information or suggestions.
        If no changes are needed, respond accordingly.
        NEVER ask for user input and NEVER expect it.
        If possible, suggest concrete code changes or additions that can be made. Be specific about what files and what lines.
        Provide code blocks where you can.
        Reply "TERMINATE" in the end when everything is done.
        """,
    "summary_assistant": """You are a helpful GitHub bot that reviews issues and generates appropriate responses.
        Analyze the issue details carefully and summarize the suggestions and changes made by other agents.
        """,
    "feedback_assistant": """You are a helpful GitHub bot that processes user feedback on previous bot responses.
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
    "generate_edit_command_assistant": """You are a helpful GitHub bot that synthesizes all discussion in an issue thread to generate a command for a bot to make edits.
        Analyze the issue details and comments carefully to generate a detailed and well-organized command.
        Ensure the command provides enough information for the downstream bot to make changes accurately.
        NEVER ask for user input and NEVER expect it.
        Provide code blocks where you can.
        Reply "TERMINATE" in the end when everything is done.
        """,
}


def register_functions(
        agent: ConversableAgent | AssistantAgent | UserProxyAgent,
        register_how: str = "llm",
        tool_funcs: list = tool_funcs,
) -> ConversableAgent | AssistantAgent | UserProxyAgent:
    """Register tool functions with the agent

    Args:
        agent: Agent to register functions with
    """
    for this_func in tool_funcs:
        if register_how == "llm":
            agent.register_for_llm(
                name=this_func.__name__,
                description=this_func.__doc__,
            )(this_func)
        elif register_how == "execution":
            agent.register_for_execution(
                name=this_func.__name__)(this_func)
        else:
            raise ValueError(
                "Invalid registration method, must be 'llm' or 'execution'")
    return agent

############################################################
# Agent creation and configuration
############################################################


def create_user_agent():
    """Create and configure the user agent"""

    user = UserProxyAgent(
        name="User",
        human_input_mode="NEVER",
        is_termination_msg=lambda x: x.get("content", "") and x.get(
            "content", "").rstrip().endswith("TERMINATE"),
        code_execution_config=False
    )

    user = register_functions(user, register_how="execution")

    return user


def create_agent(agent_name: str, llm_config: dict) -> AssistantAgent:
    """Create and configure the autogen agents"""

    agent = AssistantAgent(
        name=agent_name,
        llm_config=llm_config,
        system_message=agent_system_messages[agent_name],
    )

    agent = register_functions(agent, register_how="llm")

    return agent

############################################################
# Prompt generation
############################################################


def parse_comments(repo_name: str, repo_path: str, details: dict, issue: Issue) -> str:
    """Parse comments for the issue"""
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

    return last_comment_str, comments_str


def generate_prompt(
        agent_name: str,
        repo_name: str,
        repo_path: str,
        details: dict,
        issue: Issue,
        results_to_summarize: list = [],
        original_response: str = "",
        feedback_text: str = "",
) -> str:
    """Generate prompt for the agent"""
    last_comment_str, comments_str = parse_comments(
        repo_name, repo_path, details, issue)

    boilerplate_text = f"""
        Repository: {repo_name}
        Local path: {repo_path}
        Title: {details['title']}
        Body: {details['body']}
        {last_comment_str}
        """

    if agent_name == "file_assistant":
        return f"""Please analyze this GitHub issue and suggest files that need to be modified to address the issue.

    {boilerplate_text}

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
    elif agent_name == "edit_assistant":
        return f"""Suggest what changes can be made to resolve this issue:
    {boilerplate_text}

    {comments_str}


    Use the tools you have. Do not ask for user input or expect it.
    Do not look for files again. Use the files suggested by the previous agent.
    Provide code blocks which will address the issue where you can and suggest specific lines in specific files where changes can be made.
    Try to read the whole file to understand context where possible. If file is too large, search for specific functions or classes. If you can't find functions to classes, try reading sets of lines repeatedly.
    Reply "TERMINATE" in the end when everything is done."""

    elif agent_name == "feedback_assistant":
        return f"""Process this user feedback on the previous bot response and generate an improved response:
    Repository: {repo_name}
    Local path: {repo_path}

    Use the tools you have. Do not ask for user input or expect it.
    DO NOT SUGGEST CODE EXECUTIONS. Only make code editing suggestions.
    To find details of files use read_merged_summary or read_merged_docstrings
    If those are not functioning, use tools like search_for_file to search for .py files, or other tools you have.
    Read relevant files to understand context where possible. If file is too large, search for specific functions or classes. If you can't find functions to classes, try reading sets of lines repeatedly.
    Finish the job by suggesting specific lines in specific files where changes can be made.

    Previous Response:
    {original_response}

    User Feedback:
    {feedback_text}

    Please generate an updated response that addresses the feedback while maintaining any useful information from the original response.
    Reply "TERMINATE" when done.
    """

    elif agent_name == "summary_assistant":
        results_to_summarize = "\n".join(results_to_summarize)
        return f"Summarize the suggestions and changes made by the other agents. Repeat any code snippets as is.\n\n{results_to_summarize}\n"

    elif agent_name == "generate_edit_command_assistant":
        return f"""Please analyze this GitHub issue and generate a detailed edit command:

    {boilerplate_text}

    Generate a specific and detailed edit command that captures all instructions to perform the necessary changes.
    Include file paths, line numbers, and exact code changes where possible.
    Format the command in a way that can be parsed by automated tools.
    First try searching for files to get paths.

    Format your output with the following structure:
    - Summary of user's issues and requests
    - Overview of plan to address the issues
    - Specific details of changes to be made

    {comments_str}

    Reply "TERMINATE" in the end when everything is done.
    """
