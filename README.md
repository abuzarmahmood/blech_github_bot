[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/abuzarmahmood/blech_github_bot/main.svg)](https://results.pre-commit.ci/latest/github/abuzarmahmood/blech_github_bot/main)

# GitHub Monitor Bot

A Python bot that monitors GitHub repositories and automatically responds to issues using OpenAI's GPT-4 through Autogen. The bot analyzes issues, suggests relevant files and code changes, and provides detailed responses.

## Features

- Monitors configured GitHub repositories from `config/repos.txt`
- Automatically responds to issues with the `blech_bot` label or title mention
- Analyzes issue content using GPT-4o
- Suggests relevant files and code changes
- Clones and updates local repository copies
- Provides detailed code review and suggestions
- Tracks response history to avoid duplicates
- Creates development branches and pull requests from issues
- Implements changes automatically using Aider
- Processes user feedback on responses and pull requests
- Extracts and analyzes content from URLs in issues
- Self-updates while preserving configuration

## Requirements

- Python 3.8+
- OpenAI API key
- GitHub API access token
- GitHub CLI (gh)
- Aider CLI
- Required Python packages (see requirements.txt):
  - pyautogen
  - PyGithub
  - python-dotenv
  - gitpython
  - requests
  - pyyaml
  - urlextract
  - beautifulsoup4
  - aider-chat

## Setup

1. Clone the repository:
```bash
git clone https://github.com/abuzarmahmood/blech_github_bot.git
cd blech_github_bot
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Linux/Mac
# OR
.\venv\Scripts\activate  # On Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file with your API tokens:
```
GITHUB_TOKEN=your_github_token_here
OPENAI_API_KEY=your_openai_key_here
```

5. Configure repositories to monitor in `config/repos.txt`:
```
owner/repo1
owner/repo2
```

6. Configure bot behavior in `config/params.json`:
```json
{
    "auto_update": true
}
```
- `auto_update`: Controls whether the bot automatically updates itself with the latest changes from its repository. Set to `true` to enable auto-updates or `false` to disable them.

## Usage

Run the bot:
```bash
python src/response_agent.py
```

The bot will:
1. Connect to GitHub using your API token
2. Clone/update configured repositories locally
3. Process open issues that:
   - Have the `blech_bot` label or "[ blech_bot ]" in the title
   - Don't already have a bot response (for new issues)
   - Have user feedback (for follow-up responses)
   - Have development commands (for creating PRs)
4. Generate and post responses using GPT-4o
5. Create branches and PRs when requested with "[ develop_issue ]" command
6. Apply changes automatically using Aider when feedback is provided on PRs

## Code Structure

- `src/response_agent.py`: Main bot logic and Autogen agents
- `src/git_utils.py`: GitHub API interaction utilities
- `src/bot_tools.py`: Helper functions for file operations
- `src/agents.py`: Agent definitions and prompt generation
- `src/branch_handler.py`: Git branch management utilities
- `src/triggers.py`: Issue trigger detection functions
- `src/run_response_agent.sh`: Script for continuous bot operation
- `config/repos.txt`: List of repositories to monitor
- `config/params.json`: Bot configuration parameters

## Get Started

1. Set up your environment:
```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

2. Install required CLI tools:
```bash
# Install GitHub CLI
# For Linux: https://github.com/cli/cli/blob/trunk/docs/install_linux.md
# For macOS: brew install gh
# For Windows: winget install GitHub.cli

# Install Aider
pip install aider-chat
```

3. Configure your environment variables in `.env`:
```
GITHUB_TOKEN=your_github_token
OPENAI_API_KEY=your_openai_key
```

4. Add repositories to monitor in `config/repos.txt`:
```
owner/repo1
owner/repo2
```

5. Configure bot behavior in `config/params.json`:
```json
{
    "auto_update": true  # Enable/disable bot self-updates
}
```

5. Run the bot:
```bash
# Run once
python src/response_agent.py

# Or run continuously with the shell script
./src/run_response_agent.sh --delay 300  # Check every 5 minutes
```

## AI Agent Architecture

The bot uses specialized GPT-4o agents working together through Autogen:

- **File Assistant**: Analyzes repository structure
  - Reviews issue content and codebase
  - Uses repository tools to locate relevant files
  - Provides file paths and functional descriptions
  - Leverages merged summaries and docstrings

- **Edit Assistant**: Proposes code changes
  - Reviews files identified by File Assistant
  - Suggests concrete modifications with line numbers
  - Provides implementation details and code snippets
  - Uses repository tools to validate changes

- **Summary Assistant**: Creates final responses
  - Combines insights from other agents
  - Generates clear, actionable summaries
  - Maintains technical accuracy
  - Ensures consistent response format

- **Feedback Assistant**: Handles user feedback
  - Processes user comments on bot responses
  - Improves suggestions based on feedback
  - Maintains context from original response
  - Generates updated recommendations

- **Comment Summary Assistant**: Summarizes issue comments
  - Extracts relevant information from comment threads
  - Identifies key points and requirements
  - Provides concise summaries for other agents

- **Generate Edit Command Assistant**: Creates Aider commands
  - Converts discussion into actionable edit instructions
  - Generates precise commands for automated implementation
  - Formats instructions for Aider compatibility

The agents work together to:
1. Analyze issues and identify affected files
2. Propose specific code changes
3. Generate comprehensive responses
4. Process user feedback and improve suggestions
5. Automatically implement changes via Aider
6. Create and manage pull requests

## Contributing

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## License

MIT License - See LICENSE file for details
