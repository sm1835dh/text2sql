"""
PostgreSQL connection manager using SQLAlchemy.
"""

from typing import Any, Dict, List, Optional, Union, Tuple
from contextlib import contextmanager
import pandas as pd

from sqlalchemy import (
    create_engine, text, MetaData, Table, inspect,
    Engine, Connection, pool as sqlalchemy_pool
)
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError, OperationalError

from src.connections.base import AbstractConnectionManager
from src.utils.logger import get_logger
from src.utils.decorators import retry, cache_result, monitor_performance
from src.utils.exceptions import (
    ConnectionError, SQLExecutionError, SchemaError
)
from src.config.settings import get_settings

logger = get_logger()


class PostgreSQLConnection(AbstractConnectionManager):
    """
    PostgreSQL connection manager with SQLAlchemy.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        """
        Initialize PostgreSQL connection.

        Args:
            config: Optional configuration override
            **kwargs: Additional connection parameters
        """
        # Get configuration
        settings = get_settings()
        if config is None:
            config = {
                'host': settings.database.host,
                'port': settings.database.port,
                'database': settings.database.database,
                'user': settings.database.user,
                'password': settings.database.password.get_secret_value(),
                'pool_size': settings.database.pool_size,
                'max_overflow': settings.database.max_overflow,
                'pool_timeout': settings.database.pool_timeout,
                'pool_recycle': settings.database.pool_recycle,
                'echo': settings.database.echo,
            }

        # SQLAlchemy specific attributes
        self.engine: Optional[Engine] = None
        self.metadata: Optional[MetaData] = None
        self.session_maker: Optional[sessionmaker] = None
        self._schema_cache: Dict[str, Any] = {}

        # Initialize base class
        super().__init__(
            config=config,
            pool_size=config.get('pool_size', 10),
            max_overflow=config.get('max_overflow', 20),
            pool_timeout=config.get('pool_timeout', 30),
            pool_recycle=config.get('pool_recycle', 3600),
        )

    def _create_connection(self) -> Engine:
        """
        Create SQLAlchemy engine.

        Returns:
            SQLAlchemy Engine instance
        """
        # Build connection URL
        url = (
            f"postgresql://{self.config['user']}:{self.config['password']}"
            f"@{self.config['host']}:{self.config['port']}/{self.config['database']}"
        )

        # Create engine with connection pooling
        engine = create_engine(
            url,
            poolclass=sqlalchemy_pool.QueuePool,
            pool_size=self.config.get('pool_size', 10),
            max_overflow=self.config.get('max_overflow', 20),
            pool_timeout=self.config.get('pool_timeout', 30),
            pool_recycle=self.config.get('pool_recycle', 3600),
            pool_pre_ping=True,  # Verify connections before using
            echo=self.config.get('echo', False),
            connect_args={
                'connect_timeout': self.config.get('pool_timeout', 30),
                'application_name': 'text2sql-langgraph',
            }
        )

        # Store engine reference
        if self.engine is None:
            self.engine = engine
            self.metadata = MetaData()
            self.session_maker = sessionmaker(bind=engine)

        return engine

    @retry(max_attempts=3, exceptions=(OperationalError,))
    def health_check(self) -> bool:
        """
        Check PostgreSQL connection health.

        Returns:
            True if healthy
        """
        try:
            with self.get_connection() as conn:
                result = conn.execute(text("SELECT 1"))
                return result.scalar() == 1
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    @monitor_performance(threshold_ms=1000)
    def execute(
        self,
        query: Union[str, text],
        params: Optional[Dict[str, Any]] = None,
        fetch: bool = True,
        commit: bool = False,
    ) -> Any:
        """
        Execute SQL query.

        Args:
            query: SQL query string or SQLAlchemy text object
            params: Query parameters
            fetch: Whether to fetch results
            commit: Whether to commit transaction

        Returns:
            Query results or None

        Raises:
            SQLExecutionError: If query execution fails
        """
        try:
            # Convert string to text object if needed
            if isinstance(query, str):
                query = text(query)

            with self.get_connection() as conn:
                # Execute query
                if params:
                    result = conn.execute(query, params)
                else:
                    result = conn.execute(query)

                # Commit if requested
                if commit:
                    conn.commit()

                # Fetch results if requested
                if fetch and result.returns_rows:
                    return result.fetchall()

                return result

        except SQLAlchemyError as e:
            logger.error(f"SQL execution error: {e}")
            raise SQLExecutionError(
                f"Failed to execute query: {str(e)}",
                query=str(query),
                original_error=str(e)
            )

    def execute_df(
        self,
        query: Union[str, text],
        params: Optional[Dict[str, Any]] = None,
    ) -> pd.DataFrame:
        """
        Execute query and return results as DataFrame.

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            Query results as DataFrame
        """
        try:
            if isinstance(query, text):
                query = str(query)

            with self.engine.connect() as conn:
                return pd.read_sql_query(query, conn, params=params)

        except Exception as e:
            logger.error(f"Failed to execute query as DataFrame: {e}")
            raise SQLExecutionError(
                f"Failed to execute query: {str(e)}",
                query=query,
                original_error=str(e)
            )

    @contextmanager
    def get_session(self) -> Session:
        """
        Get SQLAlchemy session.

        Yields:
            SQLAlchemy Session instance
        """
        session = self.session_maker()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @contextmanager
    def transaction(self):
        """
        Execute within a transaction.

        Yields:
            Connection instance
        """
        with self.engine.begin() as conn:
            yield conn

    @cache_result(ttl=3600)
    def get_schema_info(self, refresh: bool = False) -> Dict[str, Any]:
        """
        Get database schema information.

        Args:
            refresh: Force refresh cache

        Returns:
            Schema information dictionary
        """
        if not refresh and self._schema_cache:
            return self._schema_cache

        try:
            inspector = inspect(self.engine)
            schema_info = {
                'tables': {},
                'views': [],
                'indexes': {},
                'foreign_keys': {},
            }

            # Get all tables
            for table_name in inspector.get_table_names():
                # Get columns
                columns = []
                for col in inspector.get_columns(table_name):
                    columns.append({
                        'name': col['name'],
                        'type': str(col['type']),
                        'nullable': col['nullable'],
                        'default': col.get('default'),
                        'primary_key': col.get('primary_key', False),
                    })

                # Get primary keys
                pk_constraint = inspector.get_pk_constraint(table_name)
                primary_keys = pk_constraint.get('constrained_columns', [])

                # Get foreign keys
                foreign_keys = []
                for fk in inspector.get_foreign_keys(table_name):
                    foreign_keys.append({
                        'name': fk.get('name'),
                        'columns': fk['constrained_columns'],
                        'referred_table': fk['referred_table'],
                        'referred_columns': fk['referred_columns'],
                    })

                # Get indexes
                indexes = []
                for idx in inspector.get_indexes(table_name):
                    indexes.append({
                        'name': idx['name'],
                        'columns': idx['column_names'],
                        'unique': idx['unique'],
                    })

                schema_info['tables'][table_name] = {
                    'columns': columns,
                    'primary_keys': primary_keys,
                    'foreign_keys': foreign_keys,
                    'indexes': indexes,
                }

            # Get views
            schema_info['views'] = inspector.get_view_names()

            # Cache the schema
            self._schema_cache = schema_info
            return schema_info

        except Exception as e:
            logger.error(f"Failed to get schema info: {e}")
            raise SchemaError(f"Failed to retrieve schema information: {str(e)}")

    def get_table_columns(self, table_name: str) -> List[str]:
        """
        Get column names for a table.

        Args:
            table_name: Name of the table

        Returns:
            List of column names
        """
        schema_info = self.get_schema_info()
        if table_name not in schema_info['tables']:
            raise SchemaError(f"Table '{table_name}' not found", table=table_name)

        return [col['name'] for col in schema_info['tables'][table_name]['columns']]

    def table_exists(self, table_name: str) -> bool:
        """
        Check if table exists.

        Args:
            table_name: Name of the table

        Returns:
            True if table exists
        """
        schema_info = self.get_schema_info()
        return table_name in schema_info['tables']

    def get_table_row_count(self, table_name: str) -> int:
        """
        Get row count for a table.

        Args:
            table_name: Name of the table

        Returns:
            Number of rows
        """
        if not self.table_exists(table_name):
            raise SchemaError(f"Table '{table_name}' not found", table=table_name)

        query = f"SELECT COUNT(*) FROM {table_name}"
        result = self.execute(query, fetch=True)
        return result[0][0] if result else 0

    def get_sample_data(
        self,
        table_name: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get sample data from a table.

        Args:
            table_name: Name of the table
            limit: Number of rows to fetch

        Returns:
            List of row dictionaries
        """
        if not self.table_exists(table_name):
            raise SchemaError(f"Table '{table_name}' not found", table=table_name)

        query = f"SELECT * FROM {table_name} LIMIT :limit"
        result = self.execute(query, params={'limit': limit}, fetch=True)

        # Convert to list of dictionaries
        columns = self.get_table_columns(table_name)
        return [dict(zip(columns, row)) for row in result]

    def validate_query(self, query: str) -> Tuple[bool, Optional[str]]:
        """
        Validate SQL query without executing.

        Args:
            query: SQL query to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Use EXPLAIN to validate without executing
            explain_query = f"EXPLAIN {query}"
            self.execute(explain_query, fetch=False)
            return True, None
        except SQLExecutionError as e:
            return False, str(e)

    def bulk_insert(
        self,
        table_name: str,
        data: List[Dict[str, Any]],
        chunk_size: int = 1000
    ) -> int:
        """
        Bulk insert data into table.

        Args:
            table_name: Name of the table
            data: List of row dictionaries
            chunk_size: Insert chunk size

        Returns:
            Number of rows inserted
        """
        if not data:
            return 0

        if not self.table_exists(table_name):
            raise SchemaError(f"Table '{table_name}' not found", table=table_name)

        rows_inserted = 0

        try:
            # Get table metadata
            table = Table(table_name, self.metadata, autoload_with=self.engine)

            # Insert in chunks
            with self.engine.begin() as conn:
                for i in range(0, len(data), chunk_size):
                    chunk = data[i:i + chunk_size]
                    conn.execute(table.insert(), chunk)
                    rows_inserted += len(chunk)

                    if i % (chunk_size * 10) == 0:
                        logger.debug(f"Inserted {rows_inserted}/{len(data)} rows")

            logger.info(f"Successfully inserted {rows_inserted} rows into {table_name}")
            return rows_inserted

        except Exception as e:
            logger.error(f"Bulk insert failed: {e}")
            raise SQLExecutionError(
                f"Failed to bulk insert into {table_name}: {str(e)}",
                query=f"INSERT INTO {table_name}",
                original_error=str(e)
            )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"PostgreSQLConnection(host={self.config['host']}, "
            f"database={self.config['database']}, "
            f"pool_size={self.pool_size})"
        )