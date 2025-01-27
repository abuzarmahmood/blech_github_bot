#!/bin/bash

# Navigate to the script directory
cd "$(dirname "$0")"

# Activate virtual environment if it exists
if [ -f "../venv/bin/activate" ]; then
    source ../venv/bin/activate
fi

# Run the response_agent.py script
python3 src/response_agent.py

# Deactivate virtual environment if it was activated
if [ -n "$VIRTUAL_ENV" ]; then
    deactivate
fi
