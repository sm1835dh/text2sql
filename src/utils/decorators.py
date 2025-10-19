"""
Collection of decorators for common functionality.
"""

import time
import functools
import hashlib
import json
import asyncio
from typing import Any, Callable, Dict, Optional, Type, Union, Tuple, List
from datetime import datetime, timedelta
from collections import defaultdict
from threading import Lock

from tenacity import (
    retry as tenacity_retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
from pydantic import BaseModel, ValidationError
from cachetools import TTLCache

from src.utils.logger import get_logger

logger = get_logger()


# Cache storage
_cache_storage: Dict[str, TTLCache] = {}
_cache_lock = Lock()

# Rate limiting storage
_rate_limit_storage: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
    'tokens': 0,
    'last_refill': datetime.now(),
    'lock': Lock()
})


def retry(
    max_attempts: int = 3,
    backoff_factor: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable] = None
):
    """
    Retry decorator with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts
        backoff_factor: Exponential backoff factor
        exceptions: Tuple of exceptions to retry on
        on_retry: Optional callback function on retry

    Returns:
        Decorated function
    """
    def decorator(func):
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            attempt = 0
            delay = 1

            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    attempt += 1
                    if attempt >= max_attempts:
                        logger.error(f"Max retries ({max_attempts}) reached for {func.__name__}")
                        raise

                    # Calculate next delay
                    delay *= backoff_factor
                    logger.warning(
                        f"Attempt {attempt}/{max_attempts} failed for {func.__name__}: {str(e)}. "
                        f"Retrying in {delay:.2f} seconds..."
                    )

                    if on_retry:
                        on_retry(e, attempt)

                    time.sleep(delay)

            return None  # Should never reach here

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            attempt = 0
            delay = 1

            while attempt < max_attempts:
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    attempt += 1
                    if attempt >= max_attempts:
                        logger.error(f"Max retries ({max_attempts}) reached for {func.__name__}")
                        raise

                    # Calculate next delay
                    delay *= backoff_factor
                    logger.warning(
                        f"Attempt {attempt}/{max_attempts} failed for {func.__name__}: {str(e)}. "
                        f"Retrying in {delay:.2f} seconds..."
                    )

                    if on_retry:
                        on_retry(e, attempt)

                    await asyncio.sleep(delay)

            return None  # Should never reach here

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def cache_result(
    ttl: int = 3600,
    cache_key_func: Optional[Callable] = None,
    cache_backend: str = "memory"
):
    """
    Cache function results with TTL.

    Args:
        ttl: Time-to-live in seconds
        cache_key_func: Optional function to generate cache key
        cache_backend: Cache backend type (currently only 'memory')

    Returns:
        Decorated function
    """
    def decorator(func):
        cache_name = f"{func.__module__}.{func.__name__}"

        def get_cache_key(*args, **kwargs) -> str:
            """Generate cache key from function arguments."""
            if cache_key_func:
                return cache_key_func(*args, **kwargs)

            # Default cache key generation
            key_parts = [cache_name]

            # Add args to key
            for arg in args:
                if isinstance(arg, (str, int, float, bool, type(None))):
                    key_parts.append(str(arg))
                else:
                    # Hash complex objects
                    key_parts.append(hashlib.md5(str(arg).encode()).hexdigest())

            # Add kwargs to key
            for k, v in sorted(kwargs.items()):
                if isinstance(v, (str, int, float, bool, type(None))):
                    key_parts.append(f"{k}={v}")
                else:
                    key_parts.append(f"{k}={hashlib.md5(str(v).encode()).hexdigest()}")

            return ":".join(key_parts)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Get or create cache for this function
            with _cache_lock:
                if cache_name not in _cache_storage:
                    _cache_storage[cache_name] = TTLCache(maxsize=1000, ttl=ttl)
                cache = _cache_storage[cache_name]

            # Generate cache key
            cache_key = get_cache_key(*args, **kwargs)

            # Check cache
            if cache_key in cache:
                logger.debug(f"Cache hit for {func.__name__} with key: {cache_key[:50]}...")
                return cache[cache_key]

            # Execute function
            result = func(*args, **kwargs)

            # Store in cache
            cache[cache_key] = result
            logger.debug(f"Cached result for {func.__name__} with key: {cache_key[:50]}...")

            return result

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Get or create cache for this function
            with _cache_lock:
                if cache_name not in _cache_storage:
                    _cache_storage[cache_name] = TTLCache(maxsize=1000, ttl=ttl)
                cache = _cache_storage[cache_name]

            # Generate cache key
            cache_key = get_cache_key(*args, **kwargs)

            # Check cache
            if cache_key in cache:
                logger.debug(f"Cache hit for {func.__name__} with key: {cache_key[:50]}...")
                return cache[cache_key]

            # Execute function
            result = await func(*args, **kwargs)

            # Store in cache
            cache[cache_key] = result
            logger.debug(f"Cached result for {func.__name__} with key: {cache_key[:50]}...")

            return result

        # Add cache management methods
        def clear_cache():
            """Clear the cache for this function."""
            with _cache_lock:
                if cache_name in _cache_storage:
                    _cache_storage[cache_name].clear()
                    logger.info(f"Cleared cache for {func.__name__}")

        def get_cache_info():
            """Get cache statistics."""
            with _cache_lock:
                if cache_name in _cache_storage:
                    cache = _cache_storage[cache_name]
                    return {
                        'size': len(cache),
                        'maxsize': cache.maxsize,
                        'ttl': cache.ttl
                    }
            return None

        # Return appropriate wrapper based on function type
        wrapper = async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
        wrapper.clear_cache = clear_cache
        wrapper.get_cache_info = get_cache_info

        return wrapper

    return decorator


def validate_input(
    model: Optional[Type[BaseModel]] = None,
    validate_return: bool = False,
    strict: bool = True
):
    """
    Validate function input using Pydantic models.

    Args:
        model: Pydantic model for validation
        validate_return: Whether to validate return value
        strict: Whether to raise on validation error

    Returns:
        Decorated function
    """
    def decorator(func):
        # Try to infer model from type hints if not provided
        nonlocal model
        if model is None:
            import inspect
            sig = inspect.signature(func)
            annotations = sig.parameters
            # Try to find a Pydantic model in the parameters
            for param_name, param in annotations.items():
                if hasattr(param.annotation, '__mro__'):
                    if BaseModel in param.annotation.__mro__:
                        model = param.annotation
                        break

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Validate input if model is provided
            if model:
                try:
                    # Combine args and kwargs for validation
                    import inspect
                    sig = inspect.signature(func)
                    bound = sig.bind(*args, **kwargs)
                    bound.apply_defaults()

                    # Validate using model
                    validated_data = model(**bound.arguments)

                    # Update kwargs with validated data
                    kwargs.update(validated_data.model_dump())
                    args = ()  # Clear args as they're now in kwargs

                except ValidationError as e:
                    logger.error(f"Input validation failed for {func.__name__}: {e}")
                    if strict:
                        raise
                    # If not strict, continue with original arguments

            # Execute function
            result = func(*args, **kwargs)

            # Validate return value if requested
            if validate_return and model:
                try:
                    model(**result) if isinstance(result, dict) else model(result)
                except ValidationError as e:
                    logger.error(f"Return validation failed for {func.__name__}: {e}")
                    if strict:
                        raise

            return result

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Similar validation for async functions
            if model:
                try:
                    import inspect
                    sig = inspect.signature(func)
                    bound = sig.bind(*args, **kwargs)
                    bound.apply_defaults()

                    validated_data = model(**bound.arguments)
                    kwargs.update(validated_data.model_dump())
                    args = ()

                except ValidationError as e:
                    logger.error(f"Input validation failed for {func.__name__}: {e}")
                    if strict:
                        raise

            result = await func(*args, **kwargs)

            if validate_return and model:
                try:
                    model(**result) if isinstance(result, dict) else model(result)
                except ValidationError as e:
                    logger.error(f"Return validation failed for {func.__name__}: {e}")
                    if strict:
                        raise

            return result

        # Return appropriate wrapper
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator


def monitor_performance(
    log_memory: bool = False,
    log_cpu: bool = False,
    threshold_ms: Optional[float] = None
):
    """
    Monitor function performance metrics.

    Args:
        log_memory: Whether to log memory usage
        log_cpu: Whether to log CPU usage
        threshold_ms: Log warning if execution exceeds threshold (milliseconds)

    Returns:
        Decorated function
    """
    def decorator(func):
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Start monitoring
            start_time = time.perf_counter()

            # Memory tracking
            if log_memory:
                import psutil
                import os
                process = psutil.Process(os.getpid())
                mem_before = process.memory_info().rss / 1024 / 1024  # MB

            # CPU tracking
            if log_cpu:
                import psutil
                import os
                process = psutil.Process(os.getpid())
                cpu_before = process.cpu_percent()

            try:
                # Execute function
                result = func(*args, **kwargs)

                # Calculate metrics
                execution_time = (time.perf_counter() - start_time) * 1000  # ms

                metrics = {
                    'function': func.__name__,
                    'execution_time_ms': round(execution_time, 2)
                }

                if log_memory:
                    mem_after = process.memory_info().rss / 1024 / 1024  # MB
                    metrics['memory_delta_mb'] = round(mem_after - mem_before, 2)
                    metrics['memory_current_mb'] = round(mem_after, 2)

                if log_cpu:
                    cpu_after = process.cpu_percent()
                    metrics['cpu_percent'] = round(cpu_after, 2)

                # Log metrics
                log_level = 'WARNING' if threshold_ms and execution_time > threshold_ms else 'DEBUG'
                getattr(logger, log_level.lower())(
                    f"Performance metrics: {json.dumps(metrics)}"
                )

                return result

            except Exception as e:
                execution_time = (time.perf_counter() - start_time) * 1000
                logger.error(
                    f"Error in {func.__name__} after {execution_time:.2f}ms: {str(e)}"
                )
                raise

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.perf_counter()

            if log_memory:
                import psutil
                import os
                process = psutil.Process(os.getpid())
                mem_before = process.memory_info().rss / 1024 / 1024

            if log_cpu:
                import psutil
                import os
                process = psutil.Process(os.getpid())
                cpu_before = process.cpu_percent()

            try:
                result = await func(*args, **kwargs)

                execution_time = (time.perf_counter() - start_time) * 1000

                metrics = {
                    'function': func.__name__,
                    'execution_time_ms': round(execution_time, 2)
                }

                if log_memory:
                    mem_after = process.memory_info().rss / 1024 / 1024
                    metrics['memory_delta_mb'] = round(mem_after - mem_before, 2)
                    metrics['memory_current_mb'] = round(mem_after, 2)

                if log_cpu:
                    cpu_after = process.cpu_percent()
                    metrics['cpu_percent'] = round(cpu_after, 2)

                log_level = 'WARNING' if threshold_ms and execution_time > threshold_ms else 'DEBUG'
                getattr(logger, log_level.lower())(
                    f"Performance metrics: {json.dumps(metrics)}"
                )

                return result

            except Exception as e:
                execution_time = (time.perf_counter() - start_time) * 1000
                logger.error(
                    f"Error in {func.__name__} after {execution_time:.2f}ms: {str(e)}"
                )
                raise

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator


def rate_limit(
    calls: int = 10,
    period: int = 60,
    scope: str = "global"
):
    """
    Rate limiting decorator using token bucket algorithm.

    Args:
        calls: Number of allowed calls
        period: Time period in seconds
        scope: Rate limit scope ('global', 'user', 'ip')

    Returns:
        Decorated function
    """
    def decorator(func):
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Determine rate limit key
            if scope == "global":
                limit_key = f"{func.__module__}.{func.__name__}"
            else:
                # Extract scope identifier from kwargs
                scope_id = kwargs.get(scope, "unknown")
                limit_key = f"{func.__module__}.{func.__name__}:{scope}:{scope_id}"

            # Get or create rate limiter for this key
            limiter = _rate_limit_storage[limit_key]

            with limiter['lock']:
                now = datetime.now()

                # Refill tokens based on elapsed time
                if 'last_refill' in limiter:
                    elapsed = (now - limiter['last_refill']).total_seconds()
                    tokens_to_add = (elapsed / period) * calls
                    limiter['tokens'] = min(calls, limiter['tokens'] + tokens_to_add)
                else:
                    limiter['tokens'] = calls

                limiter['last_refill'] = now

                # Check if we have tokens available
                if limiter['tokens'] < 1:
                    wait_time = period * (1 - limiter['tokens']) / calls
                    logger.warning(
                        f"Rate limit exceeded for {func.__name__}. "
                        f"Wait {wait_time:.2f} seconds."
                    )
                    raise RateLimitExceeded(f"Rate limit exceeded. Wait {wait_time:.2f} seconds.")

                # Consume a token
                limiter['tokens'] -= 1

            # Execute function
            return func(*args, **kwargs)

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            if scope == "global":
                limit_key = f"{func.__module__}.{func.__name__}"
            else:
                scope_id = kwargs.get(scope, "unknown")
                limit_key = f"{func.__module__}.{func.__name__}:{scope}:{scope_id}"

            limiter = _rate_limit_storage[limit_key]

            with limiter['lock']:
                now = datetime.now()

                if 'last_refill' in limiter:
                    elapsed = (now - limiter['last_refill']).total_seconds()
                    tokens_to_add = (elapsed / period) * calls
                    limiter['tokens'] = min(calls, limiter['tokens'] + tokens_to_add)
                else:
                    limiter['tokens'] = calls

                limiter['last_refill'] = now

                if limiter['tokens'] < 1:
                    wait_time = period * (1 - limiter['tokens']) / calls
                    logger.warning(
                        f"Rate limit exceeded for {func.__name__}. "
                        f"Wait {wait_time:.2f} seconds."
                    )
                    raise RateLimitExceeded(f"Rate limit exceeded. Wait {wait_time:.2f} seconds.")

                limiter['tokens'] -= 1

            return await func(*args, **kwargs)

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator


def transaction(
    rollback_on: Tuple[Type[Exception], ...] = (Exception,),
    isolation_level: Optional[str] = None
):
    """
    Database transaction management decorator.

    Args:
        rollback_on: Exceptions that trigger rollback
        isolation_level: Transaction isolation level

    Returns:
        Decorated function
    """
    def decorator(func):
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Try to extract db connection from args or kwargs
            db = None
            for arg in args:
                if hasattr(arg, 'begin') and hasattr(arg, 'commit'):
                    db = arg
                    break
            if not db:
                db = kwargs.get('db') or kwargs.get('connection') or kwargs.get('session')

            if not db:
                logger.warning(f"No database connection found for transaction in {func.__name__}")
                return func(*args, **kwargs)

            # Start transaction
            trans = db.begin()
            if isolation_level:
                db.execute(f"SET TRANSACTION ISOLATION LEVEL {isolation_level}")

            try:
                result = func(*args, **kwargs)
                trans.commit()
                logger.debug(f"Transaction committed for {func.__name__}")
                return result

            except rollback_on as e:
                trans.rollback()
                logger.warning(f"Transaction rolled back for {func.__name__}: {str(e)}")
                raise

            except Exception as e:
                trans.rollback()
                logger.error(f"Unexpected error in transaction {func.__name__}: {str(e)}")
                raise

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            db = None
            for arg in args:
                if hasattr(arg, 'begin') and hasattr(arg, 'commit'):
                    db = arg
                    break
            if not db:
                db = kwargs.get('db') or kwargs.get('connection') or kwargs.get('session')

            if not db:
                logger.warning(f"No database connection found for transaction in {func.__name__}")
                return await func(*args, **kwargs)

            async with db.begin() as trans:
                if isolation_level:
                    await db.execute(f"SET TRANSACTION ISOLATION LEVEL {isolation_level}")

                try:
                    result = await func(*args, **kwargs)
                    await trans.commit()
                    logger.debug(f"Transaction committed for {func.__name__}")
                    return result

                except rollback_on as e:
                    await trans.rollback()
                    logger.warning(f"Transaction rolled back for {func.__name__}: {str(e)}")
                    raise

                except Exception as e:
                    await trans.rollback()
                    logger.error(f"Unexpected error in transaction {func.__name__}: {str(e)}")
                    raise

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator


class RateLimitExceeded(Exception):
    """Exception raised when rate limit is exceeded."""
    pass


def error_handler(
    default_return: Any = None,
    reraise: bool = True,
    log_traceback: bool = True
):
    """
    Generic error handling decorator.

    Args:
        default_return: Default value to return on error
        reraise: Whether to re-raise the exception
        log_traceback: Whether to log the full traceback

    Returns:
        Decorated function
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(
                    f"Error in {func.__name__}: {str(e)}",
                    exc_info=log_traceback
                )
                if reraise:
                    raise
                return default_return

        return wrapper
    return decorator


def benchmark(func):
    """
    Simple benchmark decorator that logs execution time.

    Returns:
        Decorated function
    """
    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        logger.info(f"{func.__name__} took {elapsed:.4f} seconds")
        return result

    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = await func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        logger.info(f"{func.__name__} took {elapsed:.4f} seconds")
        return result

    return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper