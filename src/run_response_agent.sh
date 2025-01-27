#!/bin/bash

# Navigate to the script directory
cd "$(dirname "$0")"
echo "Directory: $(pwd)"

# Activate virtual environment if it exists
if [ -f "../venv/bin/activate" ]; then
    source ../venv/bin/activate
    echo "Virtual environment activated from" $(realpath ../venv/bin/activate)
fi

# Run the response_agent.py script
python3 response_agent.py

# Deactivate virtual environment if it was activated
if [ -n "$VIRTUAL_ENV" ]; then
    deactivate
fi
