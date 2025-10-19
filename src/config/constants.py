"""
Application constants and enumerations.
"""

from enum import Enum, auto
from typing import Dict, List, Any


class Environment(str, Enum):
    """Environment types."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(str, Enum):
    """Log levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class IntentType(str, Enum):
    """Query intent types."""
    PRICE_INQUIRY = "price_inquiry"
    COMPARISON = "comparison"
    AGGREGATION = "aggregation"
    SEARCH = "search"
    COUNT = "count"
    FILTER = "filter"
    JOIN = "join"
    RANKING = "ranking"
    TEMPORAL = "temporal"
    UNKNOWN = "unknown"


class EntityType(str, Enum):
    """Entity types for extraction."""
    PRODUCT = "product"
    BRAND = "brand"
    CATEGORY = "category"
    PRICE = "price"
    DATE = "date"
    LOCATION = "location"
    ATTRIBUTE = "attribute"
    QUANTITY = "quantity"
    CUSTOMER = "customer"
    VENDOR = "vendor"


class SQLOperationType(str, Enum):
    """SQL operation types."""
    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    CREATE = "CREATE"
    DROP = "DROP"
    ALTER = "ALTER"


class WorkflowStatus(str, Enum):
    """Workflow execution status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class NodeType(str, Enum):
    """LangGraph node types."""
    INPUT = "input"
    INTENT_CLASSIFIER = "intent_classifier"
    ENTITY_EXTRACTOR = "entity_extractor"
    KV_EXTRACTOR = "kv_extractor"
    SQL_GENERATOR = "sql_generator"
    SQL_EXECUTOR = "sql_executor"
    OUTPUT = "output"
    ERROR_HANDLER = "error_handler"


class CacheBackend(str, Enum):
    """Cache backend types."""
    MEMORY = "memory"
    REDIS = "redis"
    MEMCACHED = "memcached"


class ErrorCode(str, Enum):
    """Error codes for standardized error handling."""
    CONNECTION_ERROR = "E001"
    VALIDATION_ERROR = "E002"
    SQL_GENERATION_ERROR = "E003"
    SQL_EXECUTION_ERROR = "E004"
    INTENT_CLASSIFICATION_ERROR = "E005"
    ENTITY_EXTRACTION_ERROR = "E006"
    RATE_LIMIT_ERROR = "E007"
    TIMEOUT_ERROR = "E008"
    AUTHENTICATION_ERROR = "E009"
    UNKNOWN_ERROR = "E999"


# SQL Templates
SQL_TEMPLATES = {
    IntentType.PRICE_INQUIRY: """
        SELECT {columns}
        FROM {table}
        WHERE {conditions}
        ORDER BY {order_by}
        LIMIT {limit}
    """,
    IntentType.COMPARISON: """
        SELECT {columns}
        FROM {table1} t1
        JOIN {table2} t2 ON {join_condition}
        WHERE {conditions}
        ORDER BY {order_by}
    """,
    IntentType.AGGREGATION: """
        SELECT {group_by}, {aggregations}
        FROM {table}
        WHERE {conditions}
        GROUP BY {group_by}
        HAVING {having_conditions}
        ORDER BY {order_by}
    """,
    IntentType.COUNT: """
        SELECT COUNT({count_column}) as count
        FROM {table}
        WHERE {conditions}
    """,
}

# Default configuration values
DEFAULTS = {
    "max_retries": 3,
    "retry_delay": 1.0,
    "timeout": 30,
    "batch_size": 10,
    "cache_ttl": 3600,
    "pool_size": 10,
    "max_overflow": 20,
    "page_size": 100,
}

# Regex patterns
PATTERNS = {
    "email": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
    "phone": r"^\+?1?\d{9,15}$",
    "date": r"\d{4}-\d{2}-\d{2}",
    "time": r"\d{2}:\d{2}:\d{2}",
    "url": r"https?://[^\s]+",
    "sql_injection": r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|EXECUTE|UNION|FROM|WHERE)\b)",
}

# HTTP status codes
HTTP_STATUS = {
    "OK": 200,
    "CREATED": 201,
    "ACCEPTED": 202,
    "NO_CONTENT": 204,
    "BAD_REQUEST": 400,
    "UNAUTHORIZED": 401,
    "FORBIDDEN": 403,
    "NOT_FOUND": 404,
    "TIMEOUT": 408,
    "CONFLICT": 409,
    "UNPROCESSABLE_ENTITY": 422,
    "TOO_MANY_REQUESTS": 429,
    "INTERNAL_SERVER_ERROR": 500,
    "BAD_GATEWAY": 502,
    "SERVICE_UNAVAILABLE": 503,
}

# Database schema metadata keys
SCHEMA_METADATA_KEYS = [
    "table_name",
    "column_name",
    "data_type",
    "is_nullable",
    "column_default",
    "character_maximum_length",
    "numeric_precision",
    "numeric_scale",
    "is_primary_key",
    "is_foreign_key",
    "foreign_table",
    "foreign_column",
]

# Supported data types for validation
SUPPORTED_DATA_TYPES = {
    "postgresql": [
        "integer", "bigint", "smallint",
        "decimal", "numeric", "real", "double precision",
        "varchar", "char", "text",
        "date", "time", "timestamp", "timestamptz",
        "boolean", "json", "jsonb", "uuid",
        "array", "bytea"
    ],
    "mongodb": [
        "string", "number", "boolean",
        "object", "array", "null",
        "date", "objectId", "binary",
        "regex", "javascript", "symbol"
    ]
}

# LLM prompt templates
PROMPT_TEMPLATES = {
    "intent_classification": """
Given the following natural language question about a database:
"{question}"

Classify the intent of this question into one of the following categories:
- price_inquiry: Questions about product prices
- comparison: Comparing multiple items or values
- aggregation: Questions requiring GROUP BY operations
- search: General search queries
- count: Questions asking for counts or quantities
- filter: Questions with specific filtering criteria
- join: Questions requiring data from multiple tables
- ranking: Questions about top/bottom items
- temporal: Time-based queries
- unknown: Cannot determine the intent

Intent:
""",

    "entity_extraction": """
Extract all relevant entities from the following question:
"{question}"

Entity types to identify:
- product: Product names or IDs
- brand: Brand names
- category: Product categories
- price: Price values or ranges
- date: Dates or time periods
- location: Geographic locations
- attribute: Product attributes
- quantity: Numeric quantities
- customer: Customer names or IDs
- vendor: Vendor or supplier names

Return entities in JSON format:
""",

    "sql_generation": """
Generate a SQL query for the following request:

Question: {question}
Intent: {intent}
Entities: {entities}
Database Schema: {schema}

Requirements:
- Use only tables and columns that exist in the schema
- Include appropriate JOINs if needed
- Add ORDER BY and LIMIT clauses when relevant
- Use parameterized placeholders for values when appropriate

SQL Query:
""",

    "error_correction": """
The following SQL query failed with an error:

Query: {query}
Error: {error}
Schema: {schema}

Please correct the SQL query to fix the error.

Corrected SQL:
""",
}

# Evaluation metrics
METRICS = {
    "accuracy": ["exact_match", "semantic_match", "partial_match"],
    "performance": ["latency_p50", "latency_p95", "latency_p99", "throughput"],
    "quality": ["precision", "recall", "f1_score"],
    "errors": ["error_rate", "retry_rate", "timeout_rate"],
}

# File paths and extensions
FILE_EXTENSIONS = {
    "data": [".csv", ".tsv", ".json", ".jsonl", ".parquet"],
    "config": [".yaml", ".yml", ".json", ".toml"],
    "log": [".log", ".txt"],
    "checkpoint": [".ckpt", ".pkl", ".joblib"],
}

# Rate limiting configurations
RATE_LIMITS = {
    "azure_openai": {
        "requests_per_minute": 60,
        "tokens_per_minute": 90000,
    },
    "azure_search": {
        "requests_per_second": 10,
    },
    "database": {
        "connections_per_second": 20,
    },
}

# Validation rules
VALIDATION_RULES = {
    "question_min_length": 3,
    "question_max_length": 500,
    "sql_max_length": 10000,
    "result_max_rows": 10000,
    "timeout_seconds": 30,
}

# Feature flags
FEATURE_FLAGS = {
    "enable_caching": True,
    "enable_retry": True,
    "enable_monitoring": True,
    "enable_tracing": True,
    "enable_validation": True,
    "enable_rate_limiting": True,
    "enable_async_processing": True,
    "enable_batch_processing": True,
}