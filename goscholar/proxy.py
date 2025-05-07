# import random
# import time
# import logging
# import requests
# from functools import wraps
# from threading import RLock

# from fp.fp import FreeProxy
# from scholarly import scholarly
# from rest_framework.response import Response
# from rest_framework import status

# # Configure logging
# logger = logging.getLogger(__name__)

# # Constants
# MAX_PROXY_ATTEMPTS = 5
# MAX_RETRIES = 3

# class DirectProxyManager:
#     """
#     Manages direct proxy rotation for Google Scholar, without using scholarly.use_proxy().
#     Instead, it patches the scholarly module's internal request mechanism.
#     """
    
#     _proxies = []
#     _current_proxy_index = 0
#     _last_refresh = 0
#     _lock = RLock()
    
#     @classmethod
#     def add_random_delay(cls, min_sec=0.5, max_sec=2.0):
#         """Add a random delay to mimic human behavior and avoid rate limiting."""
#         time.sleep(random.uniform(min_sec, max_sec))
    
#     @classmethod
#     def initialize(cls, refresh=True):
#         """Initialize the proxy manager and refresh proxy list if needed."""
#         with cls._lock:
#             if refresh or not cls._proxies or time.time() - cls._last_refresh > 1800:  # 30 minutes
#                 cls.refresh_proxies()
    
#     @classmethod
#     def refresh_proxies(cls):
#         """Get a fresh list of proxies."""
#         with cls._lock:
#             new_proxies = []
#             attempts = 0
            
#             logger.info("Refreshing proxy list...")
            
#             while attempts < MAX_PROXY_ATTEMPTS and len(new_proxies) < 5:
#                 try:
#                     proxy = FreeProxy(
#                         country_id=['US', 'CA', 'GB', 'DE', 'FR'],
#                         anonym=True,
#                         https=True,
#                         timeout=5
#                     ).get()
                    
#                     if proxy and cls._test_proxy(proxy):
#                         new_proxies.append(proxy)
#                         logger.info(f"Added working proxy: {proxy}")
                    
#                 except Exception as e:
#                     logger.warning(f"Error getting proxy: {str(e)}")
                
#                 attempts += 1
#                 cls.add_random_delay(1.0, 2.0)
            
#             if new_proxies:
#                 cls._proxies = new_proxies
#                 cls._current_proxy_index = 0
#                 cls._last_refresh = time.time()
                
#                 # IMPORTANT: Apply the proxy directly to requests used by scholarly
#                 # This avoids using scholarly.use_proxy() entirely
#                 cls._patch_scholarly_requests()
                
#                 logger.info(f"Proxy list refreshed with {len(new_proxies)} proxies")
#                 return True
#             else:
#                 logger.warning("Failed to find any working proxies")
#                 return False
    
#     @classmethod
#     def _test_proxy(cls, proxy_url):
#         """Test if a proxy works with Google Scholar."""
#         try:
#             proxies = {
#                 'http': proxy_url,
#                 'https': proxy_url
#             }
            
#             headers = {
#                 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
#             }
            
#             response = requests.get(
#                 'https://scholar.google.com/citations?view_op=search_authors&mauthors=test',
#                 proxies=proxies,
#                 headers=headers,
#                 timeout=10
#             )
            
#             return response.status_code == 200
            
#         except Exception as e:
#             logger.debug(f"Proxy test failed for {proxy_url}: {str(e)}")
#             return False
    
#     @classmethod
#     def get_current_proxy(cls):
#         """Get the current proxy from the rotation list."""
#         with cls._lock:
#             if not cls._proxies:
#                 cls.refresh_proxies()
#                 if not cls._proxies:
#                     return None
            
#             return cls._proxies[cls._current_proxy_index]
    
#     @classmethod
#     def rotate_proxy(cls):
#         """Rotate to the next proxy in the list."""
#         with cls._lock:
#             if not cls._proxies:
#                 return cls.refresh_proxies()
            
#             cls._current_proxy_index = (cls._current_proxy_index + 1) % len(cls._proxies)
#             proxy = cls._proxies[cls._current_proxy_index]
            
#             # Apply the new proxy to scholarly's request mechanism
#             cls._patch_scholarly_requests()
            
#             logger.info(f"Rotated to proxy: {proxy}")
#             return True
    
#     @classmethod
#     def _patch_scholarly_requests(cls):
#         """
#         Patch the scholarly module's request mechanism to use our proxy directly.
#         This avoids using scholarly.use_proxy() completely.
#         """
#         if not cls._proxies:
#             return False
        
#         current_proxy = cls._proxies[cls._current_proxy_index]
#         proxies = {
#             'http': current_proxy,
#             'https': current_proxy
#         }
        
#         # Get the original _get_page function from scholarly's _navigator module
#         from scholarly._navigator import Navigator
        
#         # Store the original _get_page method if we haven't already
#         if not hasattr(cls, '_original_get_page'):
#             cls._original_get_page = Navigator._get_page
        
#         # Create a new _get_page function that uses our proxy
#         def patched_get_page(self, url, retries=5):
#             """Patched version of _get_page that uses our proxy."""
            
#             current_session = requests.Session()
#             current_session.proxies.update(proxies)
            
#             # Add headers to mimic a real browser
#             current_session.headers.update({
#                 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
#                 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
#                 'Accept-Language': 'en-US,en;q=0.5',
#                 'Connection': 'keep-alive',
#                 'Upgrade-Insecure-Requests': '1',
#                 'Cache-Control': 'max-age=0',
#             })
            
#             # Replace the scholarly's Navigator session with our proxy-enabled session
#             old_session = self.sess
#             self.sess = current_session
            
#             try:
#                 # Call the original _get_page but with our session
#                 result = cls._original_get_page(self, url, retries)
#                 return result
#             except Exception as e:
#                 # If we get an error, restore the original session and re-raise
#                 logger.error(f"Error in patched _get_page: {str(e)}")
#                 raise
#             finally:
#                 # Restore the original session to avoid affecting other parts of the code
#                 self.sess = old_session
        
#         # Apply our patch to the Navigator class
#         Navigator._get_page = patched_get_page
        
#         logger.info(f"Scholarly requests patched to use proxy: {current_proxy}")
#         return True

# def direct_proxy_rotation(view_func):
#     """
#     Decorator for views that handles proxy rotation without using scholarly.use_proxy().
    
#     Usage:
#         @direct_proxy_rotation
#         def my_api_view(request):
#             # Your view code here
#     """
#     @wraps(view_func)
#     def wrapper(*args, **kwargs):
#         # Initialize proxy manager if needed
#         DirectProxyManager.initialize()
        
#         retries = 0
#         last_error = None
        
#         while retries < MAX_RETRIES:
#             try:
#                 return view_func(*args, **kwargs)
#             except Exception as e:
#                 error_msg = str(e).lower()
#                 last_error = e
                
#                 # Check if error is related to blocking
#                 if any(term in error_msg for term in ["403", "blocked", "captcha", "denied"]):
#                     logger.warning(f"Request blocked. Rotating proxy. Retry {retries+1}/{MAX_RETRIES}")
#                     DirectProxyManager.rotate_proxy()
#                     retries += 1
#                     DirectProxyManager.add_random_delay(2.0, 5.0)
#                 else:
#                     # If it's not a blocking error, just raise it
#                     logger.error(f"Non-blocking error: {str(e)}")
#                     raise
        
#         logger.error(f"Failed after {MAX_RETRIES} retries")
#         return Response(
#             {"error": "Service temporarily unavailable due to rate limiting. Please try again later."},
#             status=status.HTTP_503_SERVICE_UNAVAILABLE
#         )
    
#     return wrapper