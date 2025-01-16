"""
Agent for generating responses to GitHub issues using pyautogen
"""
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
    get_issue_details
)

import bot_tools
# tool_funcs = [func for func in dir(bot_tools) if callable(getattr(bot_tools, func))]
tool_funcs = []
for func in dir(bot_tools):
    if callable(getattr(bot_tools, func)):
        tool_funcs.append(eval(f'bot_tools.{func}'))

user = autogen.UserProxyAgent(
    name="User",
    human_input_mode="NEVER",
    is_termination_msg=lambda x: x.get("content", "") and x.get("content", "").rstrip().endswith("TERMINATE"),
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
    "temperature": 0.7
}

# Create assistant agent for generating responses
file_assistant = AssistantAgent(
    name="file_assistant",
    llm_config=llm_config,
    system_message="""You are a helpful GitHub bot that reviews issues and generates appropriate responses.
    Analyze the issue details carefully check which files (if any) need to be modified.
    If not files are given by user, use the tools you have to find and suggest the files that need to be modified.
    Reply "TERMINATE" in the end when everything is done.
    """,
)

edit_assistant = AssistantAgent(
    name="edit_assistant",
    llm_config=llm_config,
    system_message="""You are a helpful GitHub bot that reviews issues and generates appropriate responses.
    Analyze the issue details carefully and suggest the changes that need to be made.
    If no changes are needed, respond accordingly.
    Reply "TERMINATE" in the end when everything is done.
    """,
)

for this_func in tool_funcs:
    file_assistant.register_for_llm(
            name = this_func.__name__, 
            description = this_func.__doc__,
            )(this_func)
    edit_assistant.register_for_llm(
            name = this_func.__name__, 
            description = this_func.__doc__,
            )(this_func)
    user.register_for_execution(
            name=this_func.__name__)(this_func)

message = 'Create a file index in blech_clust to help LLMs better understand the file structure of the repository.'

chat_results = user.initiate_chats(
    [
        {
            "recipient": file_assistant,
            "message": message, 
            "silent": False,
            "summary_method": "reflection_with_llm",
        },
        {
            "recipient": edit_assistant,
            "message": 'Suggest what changes can be made to resolve this issue',  
            "summary_method": "reflection_with_llm",
        },
    ]
)

# Get cost
sum([x['usage_including_cached_inference']['gpt-4o-2024-08-06']['cost'] for x in [x.cost for x in chat_results]])



def create_agents():
    """Create and configure the autogen agents"""
        
    
    # Create executor agent that doesn't use LLM
    executor = ConversableAgent(
        name="executor",
        llm_config=False,
        human_input_mode="NEVER"
    )
    
    return assistant, executor

def generate_issue_response(issue: Issue) -> str:
    """
    Generate an appropriate response for a GitHub issue using autogen agents
    
    Args:
        issue: The GitHub issue to respond to
        
    Returns:
        Generated response text
    """
    # Get issue details
    details = get_issue_details(issue)
    
    # Create agents
    assistant, executor = create_agents()
    
    # Construct prompt with issue details
    prompt = f"""Please analyze this GitHub issue and generate an appropriate response:

Title: {details['title']}
Body: {details['body']}
Labels: {', '.join(details['labels'])}
Assignees: {', '.join(details['assignees'])}

Generate a helpful and specific response addressing the issue contents."""

    # Get response from assistant
    chat_result = executor.initiate_chat(
        assistant,
        message=prompt,
        max_turns=1
    )
    
    # Extract response from chat history
    response = None
    for message in chat_result.chat_history:
        if message["role"] == "user":
            response = message["content"]
            break
            
    if not response:
        response = "I apologize, but I was unable to generate a response for this issue at this time."
        
    return response

def process_issue(issue: Issue) -> Tuple[bool, Optional[str]]:
    """
    Process a single issue - check if it needs response and generate one
    
    Args:
        issue: The GitHub issue to process
        
    Returns:
        Tuple of (whether response was posted, optional error message)
    """
    try:
        # Check if issue has blech_bot tag
        if not has_blech_bot_tag(issue):
            return False, "Issue does not have blech_bot tag"
            
        # Check if already responded
        if has_bot_response(issue):
            return False, "Issue already has bot response"
            
        # Generate and post response
        response = generate_issue_response(issue)
        write_issue_response(issue, response)
        return True, None
        
    except Exception as e:
        return False, f"Error processing issue: {str(e)}"

def process_repository(repo_name: str, local_path: str = "repos") -> None:
    """
    Process all open issues in a repository
    
    Args:
        repo_name: Full name of repository (owner/repo)
        local_path: Local directory path where repo should be cloned
    """
    # Initialize GitHub client
    client = get_github_client()
    repo = get_repository(client, repo_name)
    
    # Ensure repository is cloned and up to date
    repo_dir = clone_repository(repo, local_path)
    update_repository(repo_dir)
    
    # Get open issues
    open_issues = repo.get_issues(state='open')
    
    # Process each issue
    for issue in open_issues:
        success, error = process_issue(issue)
        if success:
            print(f"Successfully processed issue #{issue.number}")
        else:
            print(f"Skipped issue #{issue.number}: {error}")

if __name__ == '__main__':
    # Example usage
    repo_name = "katzlabbrandeis/blech_clust"
    process_repository(repo_name)
