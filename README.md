# Text2SQL

A simple, straightforward system for converting natural language questions into SQL queries.

## Project Status

🚀 **Freshly initialized and ready for development!**

This project has been reset to a minimal, clean state. Previous complex architecture is preserved in the `backup/complex-architecture` branch.

## Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e .

# Install dev dependencies
pip install -e ".[dev]"
```

## Project Structure

```
text2sql/
├── src/           # Source code
├── tests/         # Tests
├── .env           # Environment variables (not tracked)
└── .env.example   # Example environment variables
```

## Development

```bash
# Run the application
python -m src.main

# Run tests
pytest

# Format code
black src/ tests/
```

## Environment Variables

Copy `.env.example` to `.env` and configure:

- Database connection settings
- OpenAI API credentials
- Other service configurations

## Next Steps

Build incrementally with only what you need:

1. Database connection module
2. Simple SQL generator
3. Query executor
4. Gradual enhancements

Keep it simple. Add complexity only when needed.
