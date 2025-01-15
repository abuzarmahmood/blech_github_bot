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
    write_issue_response,
    get_issue_details
)

def create_agents():
    """Create and configure the autogen agents"""
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OpenAI API key not found in environment variables")
        
    llm_config = {
        "model": "gpt-4",
        "api_key": api_key,
        "temperature": 0.7
    }

    # Create assistant agent for generating responses
    assistant = AssistantAgent(
        name="github_assistant",
        llm_config=llm_config,
        system_message="""You are a helpful GitHub bot that reviews issues and generates appropriate responses.
        Analyze the issue details carefully and provide specific, constructive feedback.
        Be professional and courteous in your responses."""
    )
    
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
        message=prompt
    )
    
    # Extract response from chat history
    response = None
    for message in chat_result.chat_history:
        if message["role"] == "assistant":
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

def process_repository(repo_name: str) -> None:
    """
    Process all open issues in a repository
    
    Args:
        repo_name: Full name of repository (owner/repo)
    """
    # Initialize GitHub client
    client = get_github_client()
    repo = get_repository(client, repo_name)
    
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
