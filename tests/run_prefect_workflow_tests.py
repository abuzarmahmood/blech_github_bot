#!/usr/bin/env python3
"""
Script to run Prefect workflow tests for response_agent.py

This script sets up a test environment and runs all the Prefect workflows
defined in response_agent.py to ensure they work correctly.
"""
import os
import sys
import argparse
from prefect import Flow, task
from prefect.utilities.debug import raise_on_exception

# Add the src directory to the path so we can import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.response_agent import create_prefect_flow


def run_workflow_tests(test_mode=True, debug=False):
    """
    Run all Prefect workflows in test mode
    
    Args:
        test_mode: Whether to run in test mode (simulating all triggers)
        debug: Whether to run in debug mode (raising exceptions)
    """
    print("Starting Prefect workflow tests...")
    
    # Create the flow
    flow = create_prefect_flow(test_mode=test_mode)
    
    # Run the flow with exception handling based on debug mode
    if debug:
        with raise_on_exception():
            state = flow.run()
    else:
        state = flow.run()
    
    # Check the result
    if state.is_successful():
        print("All workflows completed successfully!")
        return True
    else:
        print("Some workflows failed:")
        for task_name, task_state in state.result.items():
            if not task_state.is_successful():
                print(f"  - {task_name}: {task_state.message}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Prefect workflow tests for response_agent.py")
    parser.add_argument("--no-test-mode", action="store_true", help="Run in normal mode instead of test mode")
    parser.add_argument("--debug", action="store_true", help="Run in debug mode (raise exceptions)")
    args = parser.parse_args()
    
    success = run_workflow_tests(test_mode=not args.no_test_mode, debug=args.debug)
    sys.exit(0 if success else 1)
