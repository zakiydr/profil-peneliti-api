"""
Decorator for applying proxy rotation to DRF views
"""
import functools
import logging
from typing import Callable

from django.conf import settings
from rest_framework.response import Response
from rest_framework import status

from .proxy_rotator import proxy_rotator

logger = logging.getLogger(__name__)

def direct_proxy_rotation(max_retries: int = 3):
    """
    Decorator for DRF views that need proxy rotation.
    
    This decorator handles proxy rotation for scholarly API calls,
    automatically retrying with different proxies on failure.
    
    Args:
        max_retries: Maximum number of retries with different proxies
        
    Returns:
        Decorated view function
    """
    def decorator(view_func: Callable):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Ensure we have a proxy configured
            if not proxy_rotator.current_proxy:
                proxy_rotator.rotate_proxy()
                
            retries = 0
            last_exception = None
            
            while retries <= max_retries:
                try:
                    # Call the original view function
                    return view_func(request, *args, **kwargs)
                    
                except Exception as e:
                    last_exception = e
                    retries += 1
                    
                    logger.warning(
                        f"Error in view {view_func.__name__} using proxy {proxy_rotator.current_proxy}: "
                        f"{str(e)}. Retry {retries}/{max_retries}"
                    )
                    
                    # Mark the current proxy as failed
                    if proxy_rotator.current_proxy:
                        proxy_rotator.mark_proxy_failed(proxy_rotator.current_proxy)
                    
                    # Rotate to a new proxy
                    if not proxy_rotator.rotate_proxy():
                        logger.error("Failed to rotate to a new proxy. No proxies available.")
                        break
            
            # If we've exhausted retries, return an error response
            error_msg = f"Request failed after {max_retries} retries with different proxies"
            if last_exception:
                error_msg += f": {str(last_exception)}"
                
            logger.error(error_msg)
            return Response(
                {"error": "Service temporarily unavailable. Please try again later."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
            
        return wrapper
    return decorator