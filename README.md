# GitHub Monitor Bot

A Python bot that monitors registered GitHub repositories and automatically responds to issues and pull requests with comments and suggested edits.

## Features

- Monitors multiple GitHub repositories
- Responds to new issues and pull requests
- Provides automated code review comments
- Suggests fixes and improvements
- Configurable response templates
- Rate limiting and API usage optimization

## Requirements

- Python 3.8+
- GitHub API access token
- Required Python packages:
  - PyGithub
  - python-dotenv
  - requests
  - pyyaml

## Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/github-monitor-bot.git
cd github-monitor-bot
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file with your GitHub token:
```
GITHUB_TOKEN=your_token_here
```

4. Configure repositories to monitor in `config.yaml`:
```yaml
repositories:
  - owner/repo1
  - owner/repo2
```

## Usage

Run the bot:
```bash
python bot.py
```

The bot will:
1. Connect to GitHub using your API token
2. Monitor configured repositories
3. Respond to new issues and PRs
4. Log all activities

## Configuration

- `config.yaml`: Repository list and monitoring settings
- `templates/`: Response templates for different events
- `rules/`: Custom rules for automated responses

## Contributing

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## License

MIT License - See LICENSE file for details
