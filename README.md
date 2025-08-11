[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/abuzarmahmood/blech_github_bot/main.svg)](https://results.pre-commit.ci/latest/github/abuzarmahmood/blech_github_bot/main)
[![codecov](https://codecov.io/gh/abuzarmahmood/blech_github_bot/branch/main/graph/badge.svg)](https://codecov.io/gh/abuzarmahmood/blech_github_bot)

# 🤖 Blech Bot: Your AI-Powered GitHub Assistant

> **Turn issues into solutions with the power of GPT-4o**

Blech Bot is a smart GitHub companion that transforms how you manage repositories. Powered by OpenAI's GPT-4o and Autogen, this intelligent bot automatically analyzes issues, suggests code changes, and even implements solutions - all while you focus on what matters most: building great software.

## ✨ Features

- 🔍 **Smart Monitoring** - Keeps an eye on your repositories listed in `config/repos.txt`
- 🏷️ **Automatic Response** - Springs into action when issues have the `blech_bot` label or mention
- 🧠 **AI-Powered Analysis** - Leverages GPT-4o to understand issue context and codebase
- 💡 **Code Suggestions** - Identifies relevant files and proposes precise code changes
- 🔄 **Repository Management** - Clones and updates local copies to stay current
- 📝 **Detailed Reviews** - Provides comprehensive code reviews and actionable suggestions
- 🧵 **Context Awareness** - Tracks conversation history to avoid repetition
- 🌿 **Branch Creation** - Automatically creates development branches from issues
- 🚀 **PR Generation** - Turns issues into pull requests with implemented solutions
- 🛠️ **Automated Implementation** - Uses Aider to apply changes directly to code
- 💬 **Feedback Processing** - Learns from user comments to improve responses
- 🔗 **URL Analysis** - Extracts and processes content from links in issues
- 🔄 **Self-Maintenance** - Updates itself while preserving your configuration

## 🧰 Requirements

- 🐍 Python 3.8+
- 🔑 OpenAI API key
- 🔐 GitHub API access token
- 🖥️ GitHub CLI (gh)
- ⚙️ Aider CLI
- 📦 Required Python packages:
  - pyautogen - *AI agent framework*
  - PyGithub - *GitHub API integration*
  - python-dotenv - *Environment management*
  - gitpython - *Git operations*
  - requests - *HTTP requests*
  - pyyaml - *Configuration parsing*
  - urlextract - *URL processing*
  - beautifulsoup4 - *Web scraping*
  - aider-chat - *Code editing*

## 🚀 Get Started in Minutes

### 1️⃣ Clone & Setup
```bash
git clone https://github.com/abuzarmahmood/blech_github_bot.git
cd blech_github_bot
```

### 2️⃣ Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Linux/Mac
# OR
.\venv\Scripts\activate  # On Windows
```

### 3️⃣ Install Everything You Need
```bash
# One command installs it all
make install

# Or install components separately
make install-deps  # Just Python dependencies
make install-aider # Just aider tool
```

### 4️⃣ Configure API Access
Create a `.env` file with your API tokens:
```
GITHUB_TOKEN=your_github_token_here
OPENAI_API_KEY=your_openai_key_here
```

### 5️⃣ Tell Blech Bot What to Monitor
Add repositories to `config/repos.txt`:
```
owner/repo1
owner/repo2
```

### 6️⃣ Fine-tune Bot Behavior
Configure in `config/params.json`:
```json
{
    "auto_update": true
}
```
> **auto_update**: Set to `true` to keep your bot current with the latest features

### 7️⃣ Launch Your Bot
```bash
# Run once
python src/response_agent.py

# Or keep it running 24/7
./src/run_response_agent.sh --delay 300  # Check every 5 minutes
```

## 🔄 How It Works

```bash
python src/response_agent.py
```

### What Happens When You Run Blech Bot:

1. 🔗 **Connects to GitHub** using your secure API token
2. 📥 **Syncs repositories** to ensure it's working with the latest code
3. 🔍 **Scans for actionable issues** that:
   - Have the `blech_bot` label or "[ blech_bot ]" in the title
   - Need an initial response (new issues)
   - Have received user feedback (requiring follow-up)
   - Contain development commands (PR creation requests)
4. 💬 **Generates intelligent responses** powered by GPT-4o
5. 🌿 **Creates branches and PRs** when triggered with "[ develop_issue ]"
6. ✏️ **Implements code changes** automatically via Aider when feedback is received

## 💡 See It In Action

### A Day in the Life of Blech Bot

#### 🛠️ Setup Phase
1. **Get Everything Ready**
   - Clone the repo and set up your environment
   - Configure your API tokens in `.env`
   - Add your repositories to `config/repos.txt`

#### 🚀 Launch Phase
2. **Start Your Assistant**
   ```bash
   python src/response_agent.py
   ```
   Or keep it running continuously:
   ```bash
   ./src/run_response_agent.sh --delay 300
   ```

#### 🔄 Working Phase
3. **Issue Analysis & Response**

   **User creates an issue:**
   > "[ blech_bot ] Feature Request: Add logging system for better debugging"

   **Blech Bot responds:**
   > "I've analyzed your logging feature request and found these relevant files:
   >
   > 1. `src/utils.py` - Current error handling
   > 2. `src/config.py` - Configuration settings
   >
   > **Recommendation:** We can implement a structured logging system using Python's `logging` module with configurable levels. Here's how we could approach this..."

4. **Automatic Implementation**

   **User comments:**
   > "[ develop_issue ] This looks good, please implement it"

   **Blech Bot creates a solution:**
   > "✅ Created branch `feature/logging-system`
   >
   > ✅ Implemented logging with configurable levels
   >
   > ✅ Pull request #42 is now open for review
   >
   > The changes include a new `logger.py` module and updates to existing files to use the new logging system."

5. **Refinement Based on Feedback**

   **User comments on PR:**
   > "Could we add file rotation to prevent logs from growing too large?"

   **Blech Bot improves the solution:**
   > "Updated PR #42 with log rotation functionality:
   > - Added `TimedRotatingFileHandler`
   > - Set 7-day rotation period
   > - Configured compression for old logs
   >
   > The changes are ready for your review."

This real-world workflow shows how Blech Bot transforms issue management into an automated, AI-powered process that saves time and improves code quality.

## 🏗️ Architecture

```
blech_github_bot/
├── 🧠 src/
│   ├── response_agent.py    # Main bot orchestration
│   ├── git_utils.py         # GitHub API interactions
│   ├── bot_tools.py         # File & utility operations
│   ├── agents.py            # AI agent definitions
│   ├── branch_handler.py    # Git branch management
│   ├── triggers.py          # Issue trigger detection
│   └── run_response_agent.sh # Continuous operation
├── ⚙️ config/
│   ├── repos.txt            # Repositories to monitor
│   └── params.json          # Bot behavior settings
└── 📚 docs/                 # Documentation
```

## 🧠 AI Agent Architecture

Blech Bot employs a team of specialized GPT-4o agents that collaborate through Autogen:

### 🔍 File Assistant
![File](https://img.shields.io/badge/Role-Repository_Analysis-blue)
- Scans repository structure with precision
- Maps issue requirements to relevant code files
- Provides context-aware file recommendations
- Extracts key documentation and function signatures

### ✏️ Edit Assistant
![Edit](https://img.shields.io/badge/Role-Code_Modification-green)
- Crafts precise code changes with line-by-line accuracy
- Suggests implementation strategies with rationale
- Provides complete code snippets ready for integration
- Validates changes against repository constraints

### 📊 Summary Assistant
![Summary](https://img.shields.io/badge/Role-Response_Generation-purple)
- Synthesizes technical insights into clear explanations
- Creates actionable, user-friendly summaries
- Maintains technical accuracy while being accessible
- Ensures consistent communication style

### 💬 Feedback Assistant
![Feedback](https://img.shields.io/badge/Role-Feedback_Processing-orange)
- Interprets user comments with contextual understanding
- Refines solutions based on developer input
- Maintains continuity between conversations
- Generates improved recommendations

### 📝 Comment Summary Assistant
![Comments](https://img.shields.io/badge/Role-Thread_Analysis-yellow)
- Distills lengthy comment threads into key points
- Identifies critical requirements and constraints
- Provides concise context for other agents
- Tracks conversation evolution

### 🛠️ Edit Command Assistant
![Commands](https://img.shields.io/badge/Role-Implementation_Automation-red)
- Translates discussions into precise edit commands
- Generates Aider-compatible implementation instructions
- Ensures accurate code transformation
- Bridges the gap between ideas and implementation

### 🔄 Collaborative Workflow
The agents form a seamless pipeline that:
1. **Analyzes** issues to understand requirements
2. **Identifies** relevant files and code sections
3. **Designs** specific code modifications
4. **Generates** comprehensive, actionable responses
5. **Processes** user feedback to refine solutions
6. **Implements** changes automatically via Aider
7. **Creates** and manages pull requests

## 👥 Contributing

We welcome contributions to make Blech Bot even better!

1. 🍴 **Fork** the repository
2. 🌿 **Create** a feature branch (`git checkout -b amazing-feature`)
3. 💻 **Code** your improvements
4. 🔄 **Commit** your changes (`git commit -m 'Add amazing feature'`)
5. 📤 **Push** to your branch (`git push origin amazing-feature`)
6. 🔍 **Open** a Pull Request

## 📄 License

MIT License - See LICENSE file for details

---

<p align="center">
  <img src="https://img.shields.io/badge/Powered%20by-GPT--4o-black?style=for-the-badge&logo=openai" alt="Powered by GPT-4o"/>
  <br/>
  <em>Transforming GitHub issues into solutions - automatically</em>
</p>
