.PHONY: help setup format lint test test-coverage run run-cli evaluate clean install-dev

help:
	@echo "Available commands:"
	@echo "  make setup         - Setup virtual environment with uv"
	@echo "  make install-dev   - Install all dependencies including dev"
	@echo "  make format        - Run Black formatter"
	@echo "  make lint          - Run Pylint"
	@echo "  make test          - Run pytest"
	@echo "  make test-coverage - Run tests with coverage"
	@echo "  make run           - Execute main application"
	@echo "  make run-cli       - Execute CLI interface"
	@echo "  make evaluate      - Run TC evaluation"
	@echo "  make clean         - Remove cached files"

# Development environment setup
setup:
	uv venv
	uv pip install -e .

install-dev:
	uv pip install -e ".[dev,web]"

# Code quality
format:
	black src/ tests/

lint:
	pylint src/

# Testing
test:
	pytest tests/ -v

test-coverage:
	pytest --cov=src --cov-report=html --cov-report=term tests/

# Running the application
run:
	python -m src.main

run-cli:
	python -m src.cli

# TC evaluation
evaluate:
	python -m src.cli evaluate --tc-dir data/test_cases/

# Clean up
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true