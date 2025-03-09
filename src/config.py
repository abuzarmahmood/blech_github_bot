"""
Configuration file for the GitHub bot
"""
import os
import random
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Define the LLM configuration
llm_config = {
    "model": "gpt-4o",
    "api_key": os.getenv('OPENAI_API_KEY'),
    "temperature": random.uniform(0, 0.2),
}

# Define repository names as a dictionary
repo_names = {
    "repo1": "owner/repo1",
    "repo2": "owner/repo2",
    # Add more repositories as needed
}


def get_tracked_repos():
    """
    Get list of tracked repositories from the repo_names dictionary

    Returns:
        List of repository names in format owner/repo
    """
    return list(repo_names.values())
