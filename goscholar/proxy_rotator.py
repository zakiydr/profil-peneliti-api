import os
import random
import time
import logging
import requests
from concurrent.futures import ThreadPoolExecutor
from scholarly import scholarly, ProxyGenerator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GitHubProxyFetcher:
    """Class to fetch and validate proxies from GitHub repositories"""
    
    # Source URLs for different proxy types
    PROXY_SOURCES ='https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/all.txt'
    
    # Test URL to validate proxies
    TEST_URL = 'https://httpbin.org/ip'
    
    def __init__(self, proxy_types=None, cache_duration=3600, max_proxies=50):
        """
        Initialize the proxy fetcher
        
        Args:
            proxy_types: List of proxy types to fetch ('socks4', 'socks5', 'mixed')
            cache_duration: How long to cache proxies before refreshing (seconds)
            max_proxies: Maximum number of proxies to validate and store
        """
        self.proxy_types = proxy_types or ['socks5', 'socks4']  # Default to SOCKS proxies
        self.cache_duration = cache_duration
        self.max_proxies = max_proxies
        self.proxies = []
        self.last_fetch_time = 0
    
    def _fetch_proxy_list(self, proxy_type):
        """Fetch proxies of specified type from GitHub"""
        try:
            url = self.PROXY_SOURCES.get(proxy_type)
            if not url:
                logger.error(f"Unknown proxy type: {proxy_type}")
                return []
                
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                logger.error(f"Failed to fetch proxies from {url}: {response.status_code}")
                return []
                
            # Parse the response text
            proxy_list = response.text.strip().split('\n')
        
            
            logger.info(f"Fetched {len(proxy_list)} {proxy_type} proxies")
            return proxy_list
            
        except Exception as e:
            logger.exception(f"Error fetching {proxy_type} proxies: {str(e)}")
            return []
    
    def _test_proxy(self, proxy):
        """Test if a proxy is working"""
        try:
            proxies = {
                'http': proxy,
                'https': proxy
            }
            
            response = requests.get(
                self.TEST_URL, 
                proxies=proxies, 
                timeout=5
            )
            
            if response.status_code == 200:
                logger.debug(f"Proxy {proxy} is valid")
                return proxy
            else:
                logger.debug(f"Proxy {proxy} failed validation with status {response.status_code}")
                return None
                
        except Exception as e:
            logger.debug(f"Proxy {proxy} validation error: {str(e)}")
            return None
    
    def _validate_proxies(self, proxy_list):
        """Validate a list of proxies in parallel"""
        valid_proxies = []
        
        # Use ThreadPoolExecutor for parallel validation
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(self._test_proxy, proxy) for proxy in proxy_list]
            
            for future in futures:
                result = future.result()
                if result:
                    valid_proxies.append(result)
                    # If we have enough valid proxies, stop validation
                    if len(valid_proxies) >= self.max_proxies:
                        break
        
        logger.info(f"Found {len(valid_proxies)} valid proxies out of {len(proxy_list)} tested")
        return valid_proxies
    
    def get_proxies(self, force_refresh=False):
        """
        Get a list of valid proxies, fetching new ones if needed
        
        Args:
            force_refresh: If True, force a refresh of the proxy list
            
        Returns:
            list: List of valid proxy URLs
        """
        current_time = time.time()
        
        # Check if we need to refresh the proxies
        if force_refresh or not self.proxies or (current_time - self.last_fetch_time) > self.cache_duration:
            logger.info("Refreshing proxy list...")
            
            all_proxies = []
            for proxy_type in self.proxy_types:
                proxies = self._fetch_proxy_list(proxy_type)
                all_proxies.extend(proxies)
                
            # Shuffle to randomize testing order
            random.shuffle(all_proxies)
            
            # Take a subset to validate to save time
            validation_subset = all_proxies[:min(len(all_proxies), self.max_proxies * 3)]
            
            # Validate the proxies
            self.proxies = self._validate_proxies(validation_subset)
            self.last_fetch_time = current_time
        
        return self.proxies


class ScholarlyProxyRotator:
    """
    A class to manage proxy rotation for the scholarly library
    using proxies fetched from GitHub
    """
    def __init__(self, rotation_interval=600, max_cache_age=3600, proxy_types=None):
        """
        Initialize the proxy rotator
        
        Args:
            rotation_interval: Time in seconds between proxy rotations
            max_cache_age: Maximum age of cached proxies before refresh
            proxy_types: Types of proxies to use ('socks4', 'socks5', 'mixed')
        """
        self.rotation_interval = rotation_interval
        self.max_cache_age = max_cache_age
        self.last_rotation_time = 0
        self.current_proxy_index = -1
        self.proxy_generator = ProxyGenerator()
        self.setup_done = False
        
        # Initialize the proxy fetcher
        self.proxy_fetcher = GitHubProxyFetcher(
            proxy_types=proxy_types or ['socks5', 'socks4'],
            cache_duration=max_cache_age
        )
        
        # Failed proxies tracking
        self.failed_proxies = set()
        
        # Apply initial proxy setup
        self.proxies = self._load_proxies()
        self.rotate_proxy()
    
    def _load_proxies(self):
        """Load and return list of available proxies"""
        # Try to get proxies from environment variable first
        proxy_list = os.environ.get('SCHOLARLY_PROXIES', '')
        if proxy_list:
            return [p.strip() for p in proxy_list.split(',') if p.strip()]
        
        # If no environment proxies, fetch from GitHub
        try:
            fetched_proxies = self.proxy_fetcher.get_proxies()
            if fetched_proxies:
                return fetched_proxies
        except Exception as e:
            logger.exception(f"Error fetching proxies: {str(e)}")
        
        # Default to our Docker proxy if no GitHub proxies
        return ['http://proxy-manager:3128']
    
    def _refresh_proxies(self):
        """Refresh the proxy list"""
        old_count = len(self.proxies)
        self.proxies = self._load_proxies()
        
        # Remove any previously failed proxies
        self.proxies = [p for p in self.proxies if p not in self.failed_proxies]
        
        logger.info(f"Refreshed proxy list: {len(self.proxies)} proxies available (was {old_count})")
        return len(self.proxies) > 0
    
    def rotate_proxy(self, force=False):
        """
        Rotate to the next proxy in the list
        
        Args:
            force: If True, force rotation regardless of time interval
            
        Returns:
            bool: True if rotation was successful
        """
        current_time = time.time()
        
        # Check if it's time to rotate
        if not force and (current_time - self.last_rotation_time) < self.rotation_interval:
            return False
            
        # Refresh proxy list if needed
        if not self.proxies or len(self.proxies) <= 1:
            self._refresh_proxies()
            
        # Select next proxy
        if not self.proxies:
            logger.warning("No proxies available for rotation")
            return False
            
        # First try to find a proxy we haven't failed with
        available_proxies = [p for p in self.proxies if p not in self.failed_proxies]
        
        # If all have failed, clear the failed list and try again
        if not available_proxies:
            logger.warning("All proxies have failed, resetting failed list")
            self.failed_proxies.clear()
            available_proxies = self.proxies
            
        # Select a random proxy from available ones
        proxy_url = random.choice(available_proxies)
        
        logger.info(f"Rotating to proxy: {proxy_url}")
        
        # Configure scholarly to use this proxy
        try:
            # Initialize a new proxy generator
            self.proxy_generator = ProxyGenerator()
            
            success = False
            
            # Configure proxy based on its type
            if proxy_url.startswith('http://') or proxy_url.startswith('https://'):
                # HTTP proxy
                success = self.proxy_generator.SingleProxy(
                    http=proxy_url,
                    https=proxy_url.replace('http:', 'https:') if proxy_url.startswith('http:') else proxy_url
                )
                
            elif proxy_url.startswith('socks4://'):
                # SOCKS4 proxy
                host_port = proxy_url.replace('socks4://', '')
                if ':' in host_port:
                    host, port = host_port.split(':')
                    success = self.proxy_generator.Socks4(
                        host=host,
                        port=int(port)
                    )
                    
            elif proxy_url.startswith('socks5://'):
                # SOCKS5 proxy
                host_port = proxy_url.replace('socks5://', '')
                if ':' in host_port:
                    host, port = host_port.split(':')
                    success = self.proxy_generator.Socks5(
                        host=host,
                        port=int(port)
                    )
                    
            else:
                # Unknown protocol
                logger.error(f"Unsupported proxy protocol: {proxy_url}")
                self.failed_proxies.add(proxy_url)
                return self.rotate_proxy(force=True)  # Try another proxy
            
            if success:
                # Apply the proxy to scholarly
                scholarly.use_proxy(self.proxy_generator)
                self.last_rotation_time = current_time
                self.setup_done = True
                logger.info(f"Proxy rotation successful")
                return True
            else:
                logger.error(f"Failed to configure proxy: {proxy_url}")
                self.failed_proxies.add(proxy_url)
                return self.rotate_proxy(force=True)  # Try another proxy
                
        except Exception as e:
            logger.exception(f"Error during proxy rotation: {str(e)}")
            self.failed_proxies.add(proxy_url)
            return self.rotate_proxy(force=True)  # Try another proxy
            
    def ensure_proxy_setup(self):
        """Ensure that a proxy is set up for scholarly"""
        if not self.setup_done:
            return self.rotate_proxy(force=True)
        return True

    def handle_error(self, error_type=None):
        """
        Handle errors by potentially rotating the proxy
        
        Args:
            error_type: Type of error encountered (optional)
            
        Returns:
            bool: True if proxy was rotated
        """
        # Mark current proxy as failed
        if self.current_proxy_index >= 0 and self.current_proxy_index < len(self.proxies):
            proxy_url = self.proxies[self.current_proxy_index]
            self.failed_proxies.add(proxy_url)
        
        # For certain errors, immediately rotate the proxy
        if error_type in ['403', 'captcha', 'timeout', 'connection']:
            logger.warning(f"Received {error_type} error, forcing proxy rotation")
            return self.rotate_proxy(force=True)
        
        # For other errors, just ensure we have a proxy but don't force rotation
        return self.ensure_proxy_setup()

# Create a global instance for easy import
proxy_rotator = ScholarlyProxyRotator()

# Export utility functions for easy use in views

def rotate_scholarly_proxy(force=False):
    """Rotate the scholarly proxy"""
    return proxy_rotator.rotate_proxy(force=force)

def handle_scholarly_error(error_type=None):
    """Handle scholarly errors with potential proxy rotation"""
    return proxy_rotator.handle_error(error_type)

def ensure_scholarly_proxy():
    """Ensure scholarly has a proxy configured"""
    return proxy_rotator.ensure_proxy_setup()

def refresh_proxy_list():
    """Force refresh of the proxy list"""
    return proxy_rotator._refresh_proxies()