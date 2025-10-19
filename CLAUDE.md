# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Text2SQL LangGraph System** - an AI-powered pipeline that converts natural language questions into SQL queries, executes them against databases, and returns results. Built with Python 3.12, LangGraph, and LangChain.

## Common Development Commands

### Environment Setup and Package Management
```bash
# Setup development environment with uv (NOT pip)
make setup   # Or: uv venv && uv pip install -e .

# Install/update dependencies
uv pip install -e .
uv pip install <package>  # Add new package
```

### Code Quality and Testing
```bash
# Format code (Black - 88 char line length)
make format  # Or: black src/ tests/

# Lint code (Pylint)
make lint    # Or: pylint src/

# Run tests
make test    # Or: pytest tests/
make test-coverage  # Or: pytest --cov=src tests/

# Run specific test
pytest tests/unit/test_module.py::test_function -v
```

### Running the Application
```bash
# Main application
make run     # Or: python -m src.main

# CLI interface
make run-cli # Or: python -m src.cli

# Evaluate test cases
make evaluate  # Or: python -m src.cli evaluate --tc-dir data/test_cases/

# Interactive mode
python -m src.cli interactive
```

### Development Workflow
```bash
# Clean cached files
make clean

# Start development server (if FastAPI is implemented)
uvicorn src.main:app --reload --port 8000

# Run Streamlit UI (if implemented)
streamlit run src/ui.py
```

## High-Level Architecture

### Core Processing Pipeline

The system follows a **LangGraph-orchestrated workflow** with these key stages:

1. **Input Processing** → 2. **Intent Classification** → 3. **Entity/KV Extraction** → 4. **SQL Generation** → 5. **SQL Execution** → 6. **Result Processing**

Each stage is a LangGraph node that can execute in parallel when possible, with automatic retry and error correction mechanisms.

### Key Architectural Patterns

#### 1. **Decorator-Based Cross-Cutting Concerns**
All modules use decorators for common functionality instead of embedding it in business logic:
- `@retry`: Automatic retry with exponential backoff
- `@cache_result`: Result caching with TTL
- `@validate_input`: Pydantic-based input validation
- `@monitor_performance`: Execution metrics collection
- `@log_execution`: Automatic entry/exit logging
- `@transaction`: Database transaction management

#### 2. **Connection Pool Architecture**
All external services (PostgreSQL, MongoDB, Azure OpenAI, Azure Search) use:
- Abstract base class `AbstractConnectionManager` for consistency
- Connection pooling with configurable limits
- Health checks and automatic reconnection
- Retry logic with exponential backoff

#### 3. **LangGraph Workflow State Management**
The workflow maintains a `WorkflowState` that flows through nodes:
```python
class WorkflowState(TypedDict):
    question: str
    intent: Optional[str]
    entities: Optional[List[Entity]]
    sql_query: Optional[str]
    result: Optional[Any]
    errors: List[str]
    metadata: Dict[str, Any]
```

#### 4. **SQL Error Recovery System**
When SQL execution fails:
1. Error is analyzed by LLM
2. SQL is automatically corrected
3. Retry up to 3 times with backoff
4. Fallback to alternative query patterns

### Module Dependencies and Data Flow

```
User Question
    ↓
[Question Input Module] - Validates and preprocesses
    ↓
[Intent Classifier] - Determines query type (price/comparison/aggregate/etc)
    ↓
[Entity Extractor] + [KV Extractor] - Parallel extraction
    ↓
[SQL Generator] - Uses schema cache + intent templates
    ↓
[SQL Executor] - With automatic retry and error correction
    ↓
Result + Product IDs
```

### External Service Integration

- **Azure OpenAI**: Powers all LLM operations (intent, entity extraction, SQL generation, error correction)
- **PostgreSQL**: Primary database for SQL execution with SQLAlchemy ORM
- **MongoDB**: Stores metadata, logs, and non-relational data
- **Azure AI Search**: Provides RAG capabilities for schema matching and entity validation

### Configuration Management

Settings are managed via Pydantic models with environment-specific overrides:
- `.env` - Local development (not tracked)
- `.env.dev` - Development environment
- `.env.prod` - Production environment

Key configuration categories:
- Database connections (pool sizes, timeouts)
- Azure service credentials and endpoints
- Application behavior (cache TTL, retry params)
- LangGraph workflow settings (max steps, parallelism)

## Project Structure Notes

### Critical Files and Their Purposes

- `src/workflow/graph.py` - Core LangGraph workflow definition with node connections and routing logic
- `src/workflow/orchestrator.py` - Manages workflow execution, batching, and monitoring
- `src/modules/sql_generator.py` - SQL generation with schema awareness and intent-based templates
- `src/modules/sql_executor.py` - Handles execution with automatic retry and error recovery
- `src/connections/base.py` - Abstract connection manager defining the interface for all connections
- `src/utils/decorators.py` - Reusable decorators that reduce code duplication across modules

### Testing Strategy

- **Unit Tests**: Each module has isolated tests with mocked dependencies
- **Integration Tests**: Test workflow end-to-end with real connections
- **Test Case Evaluation**: Predefined test cases in `data/test_cases/` for accuracy measurement
- **Performance Tests**: Measure latency (p50, p95, p99) and throughput

### Performance Optimizations

1. **Caching Layers**:
   - Result cache for identical questions
   - Schema cache to avoid repeated DB introspection
   - LLM prompt template cache

2. **Parallel Execution**:
   - Entity and KV extraction run in parallel
   - Batch processing for multiple questions
   - Async I/O for all external service calls

3. **Connection Pooling**:
   - PostgreSQL: SQLAlchemy pool with overflow
   - MongoDB: PyMongo connection pool
   - Azure services: HTTP connection reuse

## Development Guidelines

### When Adding New Modules

1. Create module in appropriate directory under `src/modules/`
2. Inherit from base classes when applicable
3. Apply relevant decorators for cross-cutting concerns
4. Add comprehensive docstrings and type hints
5. Create unit tests in `tests/unit/`
6. Update the workflow graph if it's a new processing node

### When Modifying SQL Generation

1. SQL templates are managed in `src/modules/sql_generator.py`
2. Schema information is cached - clear cache after schema changes
3. Always validate generated SQL before execution
4. Test with the evaluation system using test cases

### When Working with LangGraph Workflow

1. State transitions are defined in `src/workflow/graph.py`
2. Conditional routing based on intent or error states
3. Nodes can be marked for parallel execution
4. Use `WorkflowOrchestrator` for batch processing

### Error Handling Principles

- Never silently fail - log all errors with context
- Use specific exception types defined in `src/utils/exceptions.py`
- Implement graceful degradation where possible
- Automatic retry for transient failures (network, rate limits)
- Manual retry with LLM correction for SQL errors

## Current Development Status

The project is in **active development** with base infrastructure completed. For detailed status, see `DEVELOPMENT_STATUS.md`.

### ✅ Completed (as of last update)
- **Phase 0**: Project initialization - COMPLETE
- **Phase 1**: Base infrastructure - COMPLETE
  - Logger with rotation and colors
  - Full decorator collection
  - Configuration management with Pydantic
  - Constants and custom exceptions
- **Phase 2**: Connection management - PARTIAL
  - Base connection manager with pooling
  - PostgreSQL connection with SQLAlchemy

### 🚧 In Progress
- **Phase 2**: Remaining connections (MongoDB, Azure OpenAI, Azure Search)
- **Phase 3**: Core processing modules (all pending)

### 📋 Implementation Notes for Continuity

When resuming development:

1. **Check Status First**: Review `DEVELOPMENT_STATUS.md` for exact progress
2. **Verify Connections**: Test database connections with credentials in `.env`
3. **Continue Phase 2**: Complete remaining connection modules
4. **Start Phase 3**: Begin with Question Input module

### Key Implementation Decisions Made

1. **Singleton Logger**: Using metaclass pattern for single logger instance
2. **Connection Pooling**: Custom pool implementation with overflow handling
3. **Decorator Pattern**: Extensive use for cross-cutting concerns
4. **Schema Caching**: 1-hour TTL cache for database metadata
5. **Error Hierarchy**: Custom exceptions with retry logic

### Environment Variables Configured

From `.env` (credentials provided by user):
- PostgreSQL: Host, port, database, user, password configured
- MongoDB: Connection string for Azure Cosmos DB
- Azure OpenAI: Endpoint URL, deployment name, API key
- Embeddings: Separate endpoint for text-embedding-3-small

Total: 108 tasks across all phases, ~25 completed, targeting MVP in remaining ~14 hours of development.