#!/bin/bash

# Default delay interval in seconds
DELAY=60

# Parse command line arguments for delay
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --delay) DELAY="$2"; shift ;;
        *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
    shift
done

# Navigate to the script directory
# cd "$(dirname "$0")"
# echo "Directory: $(pwd)"

# Activate virtual environment if it exists
VENV_ACTIVATE_PATH=$(realpath ./venv/bin/activate)
if [ -f "$VENV_ACTIVATE_PATH" ]; then
    source $VENV_ACTIVATE_PATH
    echo "Virtual environment activated from" $VENV_ACTIVATE_PATH
fi

# Run the response_agent.py script in a loop with the specified delay
echo "Running response_agent.py with delay of $DELAY seconds"
while true; do
    python3 src/response_agent.py
    echo "Next run in $DELAY seconds"
    sleep "$DELAY"  # Wait for the specified delay before running again
done

# Deactivate virtual environment if it was activated
if [ -n "$VIRTUAL_ENV" ]; then
    deactivate
fi
