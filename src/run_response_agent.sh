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
cd "$(dirname "$0")"
echo "Directory: $(pwd)"

# Activate virtual environment if it exists
if [ -f "../venv/bin/activate" ]; then
    source ../venv/bin/activate
    echo "Virtual environment activated from" $(realpath ../venv/bin/activate)
fi

# Run the response_agent.py script in a loop with the specified delay
echo "Running response_agent.py with delay of $DELAY seconds"
while true; do
    python3 response_agent.py
    echo "Next run in $DELAY seconds"
    sleep "$DELAY"  # Wait for the specified delay before running again
done

# Deactivate virtual environment if it was activated
if [ -n "$VIRTUAL_ENV" ]; then
    deactivate
fi
