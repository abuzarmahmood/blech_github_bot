"""
Agent creation and configuration for the GitHub bot
"""
import os
import autogen
from autogen import ConversableAgent, AssistantAgent
import bot_tools

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
