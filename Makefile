.PHONY: all install install-deps install-aider test clean

all: install

install: install-deps install-aider

install-deps:
	@echo "Installing Python dependencies..."
	python -m pip install -r requirements.txt

install-aider:
	@echo "Installing aider..."
	python -m pip install aider-install
	aider-install

test:
	@echo "Running tests..."
	pytest

clean:
	@echo "Cleaning up..."
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name "*.egg" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".coverage" -exec rm -rf {} +
	find . -type d -name "htmlcov" -exec rm -rf {} +
	find . -type d -name "dist" -exec rm -rf {} +
	find . -type d -name "build" -exec rm -rf {} +

help:
	@echo "Available targets:"
	@echo "  all          : Install dependencies and aider (default)"
	@echo "  install      : Install dependencies and aider"
	@echo "  install-deps : Install Python dependencies from requirements.txt"
	@echo "  install-aider: Install aider tool"
	@echo "  test         : Run tests with pytest"
	@echo "  clean        : Remove Python cache files and build artifacts"
	@echo "  help         : Show this help message"
