#!/bin/bash

# Run tests with coverage
python -m pytest tests/ -v --cov=src --cov-report=term-missing

# To run specific test files:
# python -m pytest tests/test_agents.py -v

# To run integration tests only:
# python -m pytest tests/test_integration.py -v -m integration
