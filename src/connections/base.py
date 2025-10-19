"""
Abstract base class for connection managers.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List, TypeVar, Generic
from contextlib import contextmanager, asynccontextmanager
import asyncio
from datetime import datetime, timedelta
import threading
from queue import Queue, Full, Empty

from src.utils.logger import get_logger
from src.utils.decorators import retry, monitor_performance
from src.utils.exceptions import ConnectionError, TimeoutError

logger = get_logger()

T = TypeVar('T')  # Generic type for connection


class ConnectionPool(Generic[T]):
    """
    Generic connection pool implementation.
    """

    def __init__(
        self,
        create_connection_func,
        max_size: int = 10,
        min_size: int = 1,
        max_overflow: int = 10,
        timeout: int = 30,
        recycle: int = 3600,
        pre_ping: bool = True,
    ):
        """
        Initialize connection pool.

        Args:
            create_connection_func: Function to create new connections
            max_size: Maximum pool size
            min_size: Minimum pool size
            max_overflow: Maximum overflow connections
            timeout: Connection timeout in seconds
            recycle: Time to recycle connections in seconds
            pre_ping: Whether to ping before using connection
        """
        self.create_connection = create_connection_func
        self.max_size = max_size
        self.min_size = min_size
        self.max_overflow = max_overflow
        self.timeout = timeout
        self.recycle = recycle
        self.pre_ping = pre_ping

        self._pool: Queue[Dict[str, Any]] = Queue(maxsize=max_size)
        self._overflow_connections: List[T] = []
        self._created_connections = 0
        self._lock = threading.Lock()
        self._shutdown = False

        # Initialize minimum connections
        self._initialize_pool()

    def _initialize_pool(self):
        """Initialize pool with minimum connections."""
        for _ in range(self.min_size):
            try:
                conn = self.create_connection()
                self._pool.put({
                    'connection': conn,
                    'created_at': datetime.now(),
                    'last_used': datetime.now(),
                })
                self._created_connections += 1
            except Exception as e:
                logger.error(f"Failed to create initial connection: {e}")

    def _is_connection_expired(self, conn_info: Dict[str, Any]) -> bool:
        """Check if connection needs recycling."""
        if self.recycle <= 0:
            return False
        age = (datetime.now() - conn_info['created_at']).total_seconds()
        return age > self.recycle

    def _validate_connection(self, conn: T) -> bool:
        """Validate connection is still alive."""
        if not self.pre_ping:
            return True

        try:
            # Try to ping the connection
            if hasattr(conn, 'ping'):
                return conn.ping()
            elif hasattr(conn, 'is_alive'):
                return conn.is_alive()
            elif hasattr(conn, 'execute'):
                conn.execute("SELECT 1")
                return True
            return True
        except Exception as e:
            logger.debug(f"Connection validation failed: {e}")
            return False

    def get_connection(self, timeout: Optional[int] = None) -> T:
        """
        Get connection from pool.

        Args:
            timeout: Optional timeout override

        Returns:
            Connection instance

        Raises:
            TimeoutError: If timeout exceeded
            ConnectionError: If connection cannot be established
        """
        timeout = timeout or self.timeout
        start_time = datetime.now()

        while True:
            # Check if shutdown
            if self._shutdown:
                raise ConnectionError("Connection pool is shut down", service="pool")

            # Try to get from pool
            try:
                conn_info = self._pool.get(timeout=1)

                # Check if connection is expired
                if self._is_connection_expired(conn_info):
                    self._close_connection(conn_info['connection'])
                    continue

                # Validate connection
                if self._validate_connection(conn_info['connection']):
                    conn_info['last_used'] = datetime.now()
                    return conn_info['connection']
                else:
                    self._close_connection(conn_info['connection'])
                    continue

            except Empty:
                # Pool is empty, try to create new connection
                with self._lock:
                    if self._created_connections < self.max_size + self.max_overflow:
                        try:
                            conn = self.create_connection()
                            self._created_connections += 1

                            if self._created_connections > self.max_size:
                                self._overflow_connections.append(conn)

                            return conn

                        except Exception as e:
                            self._created_connections -= 1
                            logger.error(f"Failed to create connection: {e}")
                            raise ConnectionError(
                                f"Failed to create connection: {e}",
                                service="pool"
                            )

            # Check timeout
            elapsed = (datetime.now() - start_time).total_seconds()
            if elapsed > timeout:
                raise TimeoutError(
                    f"Connection pool timeout after {elapsed:.2f} seconds",
                    timeout_seconds=timeout,
                    operation="get_connection"
                )

    def return_connection(self, conn: T):
        """
        Return connection to pool.

        Args:
            conn: Connection to return
        """
        if self._shutdown:
            self._close_connection(conn)
            return

        # Check if this is an overflow connection
        if conn in self._overflow_connections:
            self._close_connection(conn)
            self._overflow_connections.remove(conn)
            with self._lock:
                self._created_connections -= 1
            return

        # Try to return to pool
        try:
            self._pool.put({
                'connection': conn,
                'created_at': datetime.now(),
                'last_used': datetime.now(),
            }, block=False)
        except Full:
            # Pool is full, close the connection
            self._close_connection(conn)
            with self._lock:
                self._created_connections -= 1

    def _close_connection(self, conn: T):
        """Close a connection safely."""
        try:
            if hasattr(conn, 'close'):
                conn.close()
            elif hasattr(conn, 'disconnect'):
                conn.disconnect()
        except Exception as e:
            logger.error(f"Error closing connection: {e}")

    def shutdown(self):
        """Shutdown the connection pool."""
        self._shutdown = True

        # Close all pooled connections
        while not self._pool.empty():
            try:
                conn_info = self._pool.get_nowait()
                self._close_connection(conn_info['connection'])
            except Empty:
                break

        # Close overflow connections
        for conn in self._overflow_connections:
            self._close_connection(conn)

        self._overflow_connections.clear()
        self._created_connections = 0

    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        return {
            'pool_size': self._pool.qsize(),
            'created_connections': self._created_connections,
            'overflow_connections': len(self._overflow_connections),
            'max_size': self.max_size,
            'max_overflow': self.max_overflow,
        }


class AbstractConnectionManager(ABC):
    """
    Abstract base class for all connection managers.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        pool_size: int = 10,
        max_overflow: int = 20,
        pool_timeout: int = 30,
        pool_recycle: int = 3600,
    ):
        """
        Initialize connection manager.

        Args:
            config: Connection configuration
            pool_size: Maximum pool size
            max_overflow: Maximum overflow connections
            pool_timeout: Timeout for getting connection from pool
            pool_recycle: Time to recycle connections
        """
        self.config = config
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.pool_timeout = pool_timeout
        self.pool_recycle = pool_recycle

        self._pool: Optional[ConnectionPool] = None
        self._is_connected = False
        self._lock = threading.Lock()

        # Initialize connection pool
        self._initialize_pool()

    def _initialize_pool(self):
        """Initialize the connection pool."""
        self._pool = ConnectionPool(
            create_connection_func=self._create_connection,
            max_size=self.pool_size,
            max_overflow=self.max_overflow,
            timeout=self.pool_timeout,
            recycle=self.pool_recycle,
        )

    @abstractmethod
    def _create_connection(self) -> Any:
        """
        Create a new connection.

        Returns:
            Connection instance
        """
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """
        Check if connection is healthy.

        Returns:
            True if healthy, False otherwise
        """
        pass

    @abstractmethod
    def execute(self, *args, **kwargs) -> Any:
        """
        Execute operation using connection.

        Returns:
            Operation result
        """
        pass

    @contextmanager
    def get_connection(self):
        """
        Context manager for getting connection from pool.

        Yields:
            Connection instance
        """
        conn = None
        try:
            conn = self._pool.get_connection(timeout=self.pool_timeout)
            yield conn
        finally:
            if conn and self._pool:
                self._pool.return_connection(conn)

    @asynccontextmanager
    async def get_connection_async(self):
        """
        Async context manager for getting connection from pool.

        Yields:
            Connection instance
        """
        conn = None
        try:
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            conn = await loop.run_in_executor(
                None,
                self._pool.get_connection,
                self.pool_timeout
            )
            yield conn
        finally:
            if conn and self._pool:
                await loop.run_in_executor(
                    None,
                    self._pool.return_connection,
                    conn
                )

    @retry(max_attempts=3, backoff_factor=2)
    def connect(self) -> bool:
        """
        Establish connection.

        Returns:
            True if successful
        """
        try:
            # Test connection
            if self.health_check():
                self._is_connected = True
                logger.info(f"Successfully connected to {self.__class__.__name__}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            raise ConnectionError(
                f"Failed to connect to {self.__class__.__name__}",
                service=self.__class__.__name__
            )

    def disconnect(self):
        """Disconnect and cleanup resources."""
        if self._pool:
            self._pool.shutdown()
        self._is_connected = False
        logger.info(f"Disconnected from {self.__class__.__name__}")

    @property
    def is_connected(self) -> bool:
        """Check if currently connected."""
        return self._is_connected

    def get_stats(self) -> Dict[str, Any]:
        """
        Get connection statistics.

        Returns:
            Dictionary of statistics
        """
        stats = {
            'is_connected': self._is_connected,
            'config': {k: v for k, v in self.config.items()
                      if 'password' not in k.lower() and 'key' not in k.lower()},
        }

        if self._pool:
            stats['pool'] = self._pool.get_stats()

        return stats

    @monitor_performance(log_memory=True, threshold_ms=1000)
    def execute_with_monitoring(self, *args, **kwargs) -> Any:
        """
        Execute operation with performance monitoring.

        Returns:
            Operation result
        """
        return self.execute(*args, **kwargs)

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()

    async def __aenter__(self):
        """Async context manager entry."""
        await asyncio.get_event_loop().run_in_executor(None, self.connect)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await asyncio.get_event_loop().run_in_executor(None, self.disconnect)