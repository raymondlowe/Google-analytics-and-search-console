"""
Shared caching utilities for GA4 and GSC modules
Provides common cache key generation, error handling, and validation functions
"""

import hashlib
import json
import time
import logging
from typing import Any, Dict, Optional, Callable
from functools import wraps


def generate_cache_key(prefix: str, func_name: str, args: tuple, kwargs: dict, typed: bool = False) -> Optional[str]:
    """
    Generate a stable cache key using SHA-256 hashing.
    
    Args:
        prefix: Module prefix (e.g., 'ga4_', 'gsc_')
        func_name: Function name
        args: Function arguments
        kwargs: Function keyword arguments
        typed: Whether to include argument types in the key
        
    Returns:
        str: Stable cache key, or None if generation fails
    """
    try:
        # Serialize arguments to JSON for stable hashing
        args_serializable = []
        for arg in args:
            if hasattr(arg, '__dict__'):
                args_serializable.append(str(arg))
            else:
                args_serializable.append(arg)
        
        cache_data = {
            'function': func_name,
            'args': args_serializable,
            'kwargs': sorted(kwargs.items())
        }
        
        if typed:
            cache_data['arg_types'] = [type(arg).__name__ for arg in args]
        
        # Create SHA-256 hash of serialized data
        cache_string = json.dumps(cache_data, sort_keys=True, default=str)
        return f"{prefix}{func_name}:{hashlib.sha256(cache_string.encode()).hexdigest()}"
        
    except (TypeError, ValueError, UnicodeDecodeError):
        # Fallback to stable hashing for non-serializable args
        try:
            fallback_string = str(args) + str(sorted(kwargs.items()))
            return f"{prefix}{func_name}:{hashlib.sha256(fallback_string.encode()).hexdigest()}"
        except Exception:
            # If all cache key generation fails, skip caching
            return None


def safe_cache_get(cache, cache_key: str, func_name: str, logger_name: str = __name__) -> Any:
    """
    Safely get a value from cache with proper error handling.
    
    Args:
        cache: Cache object
        cache_key: Cache key to retrieve
        func_name: Function name for logging
        logger_name: Logger name to use
        
    Returns:
        Cached value or None if not found or error
    """
    if not cache_key:
        return None
        
    try:
        return cache.get(cache_key)
    except Exception as e:
        logging.getLogger(logger_name).warning(f"Cache read failed for {func_name}: {e}")
        return None


def safe_cache_set(cache, cache_key: str, value: Any, expire_time: int, func_name: str, 
                  logger_name: str = __name__, tag: Optional[str] = None) -> bool:
    """
    Safely set a value in cache with proper error handling.
    
    Args:
        cache: Cache object
        cache_key: Cache key to set
        value: Value to cache
        expire_time: Expiration time in seconds
        func_name: Function name for logging
        logger_name: Logger name to use
        tag: Optional cache tag for grouping
        
    Returns:
        bool: True if successfully cached, False otherwise
    """
    if not cache_key or value is None:
        return False
        
    try:
        if tag:
            cache.set(cache_key, value, expire=expire_time, tag=tag)
        else:
            cache.set(cache_key, value, expire=expire_time)
        return True
    except Exception as e:
        logging.getLogger(logger_name).warning(f"Cache write failed for {func_name}: {e}")
        return False


def safe_cache_clear(cache, func_name: str, logger_name: str = __name__) -> bool:
    """
    Safely clear cache for a function with proper error handling.
    
    Args:
        cache: Cache object
        func_name: Function name (used as tag)
        logger_name: Logger name to use
        
    Returns:
        bool: True if successfully cleared, False otherwise
    """
    try:
        if hasattr(cache, 'evict'):
            cache.evict(func_name)
        else:
            # Fallback for caches without tag-based eviction
            keys_to_delete = [key for key in cache if func_name in key]
            for key in keys_to_delete:
                try:
                    del cache[key]
                except Exception:
                    pass
        return True
    except Exception as e:
        logging.getLogger(logger_name).warning(f"Cache clear failed for {func_name}: {e}")
        return False


def validate_cache_operations(cache, test_prefix: str = "health_check") -> bool:
    """
    Validate that basic cache operations work correctly.
    
    Args:
        cache: Cache object to test
        test_prefix: Prefix for test keys
        
    Returns:
        bool: True if cache operations work, False otherwise
    """
    try:
        test_key = f"{test_prefix}:test_{int(time.time())}"
        test_value = {"timestamp": time.time(), "test": True}
        
        # Test set
        cache.set(test_key, test_value, expire=60)
        
        # Test get
        retrieved = cache.get(test_key)
        
        # Test delete
        cache.delete(test_key)
        
        return retrieved is not None and retrieved.get("test") == True
    except Exception:
        return False


def get_cache_stats(cache, cache_name: str) -> Dict[str, Any]:
    """
    Get cache statistics with comprehensive error handling.
    
    Args:
        cache: Cache object
        cache_name: Name of the cache for reporting
        
    Returns:
        dict: Cache statistics or error information
    """
    try:
        basic_stats = {
            'cache_name': cache_name,
            'cache_size': len(cache),
            'cache_healthy': True
        }
        
        # Add additional stats if available
        if hasattr(cache, 'volume'):
            try:
                basic_stats['volume_info'] = cache.volume()
            except Exception:
                pass
                
        if hasattr(cache, 'stats'):
            try:
                basic_stats['detailed_stats'] = cache.stats()
            except Exception:
                pass
        
        # Test basic operations
        basic_stats['operations_working'] = validate_cache_operations(cache, f"{cache_name}_health")
        if not basic_stats['operations_working']:
            basic_stats['cache_healthy'] = False
            
        return basic_stats
        
    except Exception as e:
        return {
            'cache_name': cache_name,
            'cache_size': 0,
            'cache_healthy': False,
            'error': str(e)
        }