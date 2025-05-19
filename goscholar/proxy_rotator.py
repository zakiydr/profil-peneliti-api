# """
# Proxy rotator for Django applications using scholarly.
# This module handles downloading, parsing, and rotating proxies from monosans/proxy-list.
# """
# import logging
# import random
# import re
# import time
# from datetime import datetime, timedelta
# from threading import Lock
# from typing import Dict, List, Optional, Tuple, Union

# import requests
# import urllib3
# from django.conf import settings
# from scholarly import scholarly, ProxyGenerator

# # Configure logging
# logger = logging.getLogger(__name__)

# # Disable SSL warnings - only for the proxy list download
# urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# class ProxyListDownloader:
#     """Downloads and parses the proxy list from GitHub."""
    
#     PROXY_URL = "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/all.txt"
    
#     @staticmethod
#     def download_proxy_list() -> List[str]:
#         """Download the proxy list from GitHub.
        
#         Returns:
#             List of proxy strings in format "protocol://ip:port"
#         """
#         try:
#             # Use verify=False only for this specific request to avoid SSL issues
#             response = requests.get(ProxyListDownloader.PROXY_URL, 
#                                     timeout=10, 
#                                     verify=False)
#             response.raise_for_status()
            
#             # Split by newlines and filter empty lines
#             proxies = [line.strip() for line in response.text.splitlines() if line.strip()]
#             logger.info(f"Downloaded {len(proxies)} proxies from GitHub")
#             return proxies
            
#         except requests.RequestException as e:
#             logger.error(f"Error downloading proxy list: {str(e)}")
#             return []
    
#     @staticmethod
#     def parse_proxy(proxy_str: str) -> Tuple[str, str, int]:
#         """Parse a proxy string into its components.
        
#         Args:
#             proxy_str: Proxy string in format "protocol://ip:port"
            
#         Returns:
#             Tuple of (protocol, host, port)
            
#         Raises:
#             ValueError: If the proxy string is invalid
#         """
#         match = re.match(r"^(http|socks4|socks5)://([^:]+):(\d+)$", proxy_str)
#         if not match:
#             raise ValueError(f"Invalid proxy format: {proxy_str}")
        
#         protocol, host, port_str = match.groups()
#         return protocol, host, int(port_str)


# class ScholarlyProxyRotator:
#     """Manages proxy rotation for scholarly library with auto-refreshing proxy list."""
    
#     def __init__(self, refresh_interval_minutes: int = 60):
#         """Initialize the proxy rotator.
        
#         Args:
#             refresh_interval_minutes: How often to refresh the proxy list in minutes
#         """
#         self.proxies: List[str] = []
#         self.http_proxies: List[str] = []
#         self.socks4_proxies: List[str] = []
#         self.socks5_proxies: List[str] = []
#         self.last_refresh: Optional[datetime] = None
#         self.refresh_interval = timedelta(minutes=refresh_interval_minutes)
#         self.current_proxy: Optional[str] = None
#         self.lock = Lock()
#         self.failed_proxies: Dict[str, datetime] = {}
#         self.proxy_timeout_minutes = getattr(settings, "PROXY_FAILURE_TIMEOUT_MINUTES", 30)
        
#         # Initial proxy list download
#         self.refresh_proxy_list()
    
#     def refresh_proxy_list(self) -> bool:
#         """Download and refresh the proxy list.
        
#         Returns:
#             True if successful, False otherwise
#         """
#         with self.lock:
#             proxies = ProxyListDownloader.download_proxy_list()
            
#             if not proxies:
#                 logger.warning("No proxies downloaded, keeping existing list")
#                 return False
            
#             # Categorize proxies by protocol
#             self.http_proxies = []
#             self.socks4_proxies = []
#             self.socks5_proxies = []
            
#             for proxy in proxies:
#                 try:
#                     protocol, _, _ = ProxyListDownloader.parse_proxy(proxy)
#                     if protocol == "http":
#                         self.http_proxies.append(proxy)
#                     elif protocol == "socks4":
#                         self.socks4_proxies.append(proxy)
#                     elif protocol == "socks5":
#                         self.socks5_proxies.append(proxy)
#                 except ValueError:
#                     continue
            
#             # Store all valid proxies
#             self.proxies = self.http_proxies + self.socks4_proxies + self.socks5_proxies
#             self.last_refresh = datetime.now()
            
#             # Clear failed proxies that have been removed from the list
#             self.failed_proxies = {p: t for p, t in self.failed_proxies.items() 
#                                   if p in self.proxies}
            
#             logger.info(f"Refreshed proxy list: {len(self.http_proxies)} HTTP, "
#                       f"{len(self.socks4_proxies)} SOCKS4, "
#                       f"{len(self.socks5_proxies)} SOCKS5")
#             return True
    
#     def check_refresh_needed(self) -> None:
#         """Check if the proxy list needs refreshing and refresh if needed."""
#         if not self.last_refresh or \
#            datetime.now() - self.last_refresh > self.refresh_interval:
#             self.refresh_proxy_list()
    
#     def mark_proxy_failed(self, proxy: str) -> None:
#         """Mark a proxy as failed.
        
#         Args:
#             proxy: The proxy string that failed
#         """
#         with self.lock:
#             self.failed_proxies[proxy] = datetime.now()
#             logger.warning(f"Marked proxy as failed: {proxy}")
    
#     def get_available_proxies(self, proxy_type: Optional[str] = None) -> List[str]:
#         """Get available proxies filtered by type and excluding recently failed ones.
        
#         Args:
#             proxy_type: Optional proxy type filter ('http', 'socks4', 'socks5')
            
#         Returns:
#             List of available proxy strings
#         """
#         with self.lock:
#             # Remove failed proxies that have timed out
#             now = datetime.now()
#             timeout = timedelta(minutes=self.proxy_timeout_minutes)
#             self.failed_proxies = {
#                 p: t for p, t in self.failed_proxies.items()
#                 if now - t < timeout
#             }
            
#             # Get proxies of the requested type
#             if proxy_type == "http":
#                 proxies = self.http_proxies
#             elif proxy_type == "socks4":
#                 proxies = self.socks4_proxies
#             elif proxy_type == "socks5":
#                 proxies = self.socks5_proxies
#             else:
#                 proxies = self.proxies
            
#             # Filter out failed proxies
#             available = [p for p in proxies if p not in self.failed_proxies]
#             return available
    
#     def configure_scholarly_with_proxy(self, proxy: str) -> bool:
#         """Configure scholarly with the given proxy.
        
#         Args:
#             proxy: Proxy string in format "protocol://ip:port"
            
#         Returns:
#             True if configured successfully, False otherwise
#         """
#         try:
#             protocol, host, port = ProxyListDownloader.parse_proxy(proxy)
#             pg = ProxyGenerator()
            
#             if protocol == "http":
#                 success = pg.SingleProxy(
#                     http=f"http://{host}:{port}",
#                     https=f"http://{host}:{port}"
#                 )
#             elif protocol == "socks4":
#                 success = pg.SingleProxy(
#                     http=f"socks4://{host}:{port}",
#                     https=f"socks4://{host}:{port}"
#                 )
#             elif protocol == "socks5":
#                 success = pg.SingleProxy(
#                     http=f"socks5://{host}:{port}",
#                     https=f"socks5://{host}:{port}"
#                 )
#             else:
#                 logger.error(f"Unsupported protocol: {protocol}")
#                 return False
            
#             if success:
#                 scholarly.use_proxy(pg)
#                 self.current_proxy = proxy
#                 logger.info(f"Configured scholarly with proxy: {proxy}")
#                 return True
            
#             logger.warning(f"Failed to configure proxy: {proxy}")
#             return False
            
#         except (ValueError, Exception) as e:
#             logger.error(f"Error configuring proxy {proxy}: {str(e)}")
#             return False
    
#     def rotate_proxy(self, preferred_type: Optional[str] = None) -> bool:
#         """Rotate to a new proxy.
        
#         Args:
#             preferred_type: Preferred proxy type ('http', 'socks4', 'socks5')
            
#         Returns:
#             True if rotated successfully, False otherwise
#         """
#         # Check if we need to refresh the proxy list
#         self.check_refresh_needed()
        
#         # Try with preferred type
#         if preferred_type:
#             available = self.get_available_proxies(preferred_type)
#             if available:
#                 proxy = random.choice(available)
#                 if self.configure_scholarly_with_proxy(proxy):
#                     return True
        
#         # Try with any type
#         available = self.get_available_proxies()
#         if not available:
#             logger.error("No available proxies!")
#             # Force refresh the list if we're out of proxies
#             self.refresh_proxy_list()
#             available = self.get_available_proxies()
#             if not available:
#                 return False
        
#         # Shuffle and try proxies until one works
#         random.shuffle(available)
#         for proxy in available[:5]:  # Try up to 5 proxies to avoid long delays
#             if self.configure_scholarly_with_proxy(proxy):
#                 return True
        
#         logger.error("Failed to configure any proxy after multiple attempts")
#         return False


# # Global instance for use across the application
# proxy_rotator = ScholarlyProxyRotator(
#     refresh_interval_minutes=getattr(settings, "PROXY_REFRESH_INTERVAL_MINUTES", 60)
# )


# class ProxyMiddleware:
#     """Django middleware for handling proxy-related errors."""
    
#     def __init__(self, get_response):
#         self.get_response = get_response
    
#     def __call__(self, request):
#         return self.get_response(request)
    
#     def process_exception(self, request, exception):
#         """Process exceptions and rotate proxy if needed."""
#         if hasattr(exception, "__module__") and exception.__module__ == 'scholarly':
#             if proxy_rotator.current_proxy:
#                 proxy_rotator.mark_proxy_failed(proxy_rotator.current_proxy)
            
#             # Try rotating to a new proxy
#             proxy_rotator.rotate_proxy()
#             return None
#         return None