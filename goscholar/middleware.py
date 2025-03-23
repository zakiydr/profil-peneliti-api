import logging
import time
import random
from datetime import datetime, timedelta
from django.utils.deprecation import MiddlewareMixin
from django.http import HttpRequest, HttpResponse
from scholarly import scholarly
from swiftshadow.classes import ProxyInterface
from typing import Optional, Dict, List, Tuple

# Configure a dedicated logger for rate limiting
rate_logger = logging.getLogger('rate_limiting')
file_handler = logging.FileHandler('rate_limiting.log')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
rate_logger.addHandler(file_handler)
rate_logger.setLevel(logging.DEBUG)

class ProxyManager:
    """Manage a pool of proxies with health tracking and rotation strategies."""
    
    def __init__(self, countries: List[str] = ["SG"], protocols: List[str] = ["http"], max_proxies: int = 5):
        self.proxy_interface = ProxyInterface(countries=countries, protocol=protocols[0], autoRotate=False)
        self.protocols = protocols
        self.countries = countries
        self.max_proxies = max_proxies
        
        # Proxy pool with health tracking
        # Format: {proxy_string: {
        #   'failures': int, 
        #   'last_used': datetime,
        #   'success_count': int,
        #   'avg_response_time': float,
        #   'backoff_until': datetime or None
        # }}
        self.proxy_pool: Dict[str, Dict] = {}
        
        # Initialize the pool
        self._initialize_pool()
    
    def _initialize_pool(self) -> None:
        """Initialize the proxy pool with healthy proxies."""
        rate_logger.info(f"Initializing proxy pool with max size {self.max_proxies}")
        
        attempts = 0
        max_attempts = self.max_proxies * 3  # Allow for some failures
        
        while len(self.proxy_pool) < self.max_proxies and attempts < max_attempts:
            attempts += 1
            try:
                proxy_obj = self.proxy_interface.get()
                proxy_string = proxy_obj.as_string()
                
                # Only add if not already in pool
                if proxy_string not in self.proxy_pool:
                    self.proxy_pool[proxy_string] = {
                        'failures': 0,
                        'last_used': datetime.now() - timedelta(minutes=10),  # Set as not recently used
                        'success_count': 0,
                        'avg_response_time': 0.0,
                        'backoff_until': None
                    }
                    rate_logger.info(f"Added proxy {proxy_string} to pool")
                
                if len(self.proxy_pool) >= self.max_proxies:
                    break
                    
                # Add a small delay between proxy requests to avoid being blocked
                time.sleep(random.uniform(0.5, 1.5))
                
            except Exception as e:
                rate_logger.warning(f"Failed to add proxy to pool: {e}")
                time.sleep(1)  # Brief pause before retrying
        
        rate_logger.info(f"Proxy pool initialized with {len(self.proxy_pool)} proxies")
    
    def get_best_proxy(self) -> str:
        """Get the best available proxy based on health metrics."""
        now = datetime.now()
        
        # Filter out proxies in backoff period
        available_proxies = {
            proxy: data for proxy, data in self.proxy_pool.items() 
            if data['backoff_until'] is None or now > data['backoff_until']
        }
        
        if not available_proxies:
            # All proxies are in backoff, choose the one with earliest backoff expiration
            if not self.proxy_pool:
                # Empty pool, initialize it
                self._initialize_pool()
                return self.get_best_proxy()
            
            # Find proxy with earliest backoff expiration
            proxy = min(
                self.proxy_pool.items(), 
                key=lambda x: x[1]['backoff_until'] if x[1]['backoff_until'] else now
            )[0]
            
            rate_logger.warning(f"All proxies in backoff, using {proxy} with earliest expiration")
            return proxy
        
        # Prioritize proxies with:
        # 1. Fewer failures
        # 2. Not recently used
        # 3. More successful requests
        # 4. Better response times
        sorted_proxies = sorted(
            available_proxies.items(),
            key=lambda x: (
                x[1]['failures'],
                -(now - x[1]['last_used']).total_seconds(),
                -x[1]['success_count'],
                x[1]['avg_response_time']
            )
        )
        
        chosen_proxy = sorted_proxies[0][0]
        # Update last used time
        self.proxy_pool[chosen_proxy]['last_used'] = now
        
        rate_logger.debug(f"Selected proxy {chosen_proxy} (failures: {self.proxy_pool[chosen_proxy]['failures']}, successes: {self.proxy_pool[chosen_proxy]['success_count']})")
        return chosen_proxy
    
    def report_success(self, proxy: str, response_time: float) -> None:
        """Report a successful request with this proxy."""
        if proxy not in self.proxy_pool:
            rate_logger.warning(f"Success reported for unknown proxy {proxy}")
            return
            
        proxy_data = self.proxy_pool[proxy]
        
        # Update success count
        proxy_data['success_count'] += 1
        
        # Update average response time (simple moving average)
        if proxy_data['avg_response_time'] == 0:
            proxy_data['avg_response_time'] = response_time
        else:
            proxy_data['avg_response_time'] = (
                proxy_data['avg_response_time'] * 0.9 + response_time * 0.1
            )
            
        rate_logger.debug(f"Success with proxy {proxy}, response time: {response_time:.2f}s")
    
    def report_failure(self, proxy: str, error_type: str) -> None:
        """Report a failed request with this proxy and apply exponential backoff."""
        if proxy not in self.proxy_pool:
            rate_logger.warning(f"Failure reported for unknown proxy {proxy}")
            return
            
        proxy_data = self.proxy_pool[proxy]
        proxy_data['failures'] += 1
        
        # Apply exponential backoff based on failure count
        backoff_seconds = min(2 ** proxy_data['failures'], 3600)  # Max 1 hour backoff
        
        # Add jitter to prevent thundering herd problem
        jitter = random.uniform(0.75, 1.25)
        backoff_seconds = backoff_seconds * jitter
        
        proxy_data['backoff_until'] = datetime.now() + timedelta(seconds=backoff_seconds)
        
        rate_logger.warning(
            f"Failure with proxy {proxy}, error: {error_type}, "
            f"failures: {proxy_data['failures']}, "
            f"backoff: {backoff_seconds:.1f}s"
        )
        
        # If a proxy has failed too many times, try to replace it
        if proxy_data['failures'] >= 5:
            self._try_replace_proxy(proxy)
    
    def _try_replace_proxy(self, proxy_to_replace: str) -> None:
        """Try to replace a failing proxy with a new one."""
        rate_logger.info(f"Attempting to replace proxy {proxy_to_replace} due to excessive failures")
        
        try:
            proxy_obj = self.proxy_interface.get()
            new_proxy = proxy_obj.as_string()
            
            # Don't replace with a proxy already in the pool
            if new_proxy in self.proxy_pool:
                rate_logger.debug(f"New proxy {new_proxy} already in pool, not replacing")
                return
                
            # Remove the failing proxy and add the new one
            if proxy_to_replace in self.proxy_pool:
                del self.proxy_pool[proxy_to_replace]
                
            self.proxy_pool[new_proxy] = {
                'failures': 0,
                'last_used': datetime.now(),
                'success_count': 0,
                'avg_response_time': 0.0,
                'backoff_until': None
            }
            
            rate_logger.info(f"Successfully replaced proxy {proxy_to_replace} with {new_proxy}")
            
        except Exception as e:
            rate_logger.error(f"Failed to replace proxy {proxy_to_replace}: {e}")
    
    def get_pool_health(self) -> Dict:
        """Return information about the health of the proxy pool."""
        total_proxies = len(self.proxy_pool)
        available_proxies = sum(
            1 for data in self.proxy_pool.values() 
            if data['backoff_until'] is None or datetime.now() > data['backoff_until']
        )
        
        return {
            'total_proxies': total_proxies,
            'available_proxies': available_proxies,
            'total_failures': sum(data['failures'] for data in self.proxy_pool.values()),
            'total_successes': sum(data['success_count'] for data in self.proxy_pool.values()),
            'avg_response_time': sum(data['avg_response_time'] for data in self.proxy_pool.values()) / max(total_proxies, 1)
        }


class RateLimitDetector:
    """Detect rate limiting based on response patterns and headers."""
    
    # Common rate limit response patterns
    RATE_LIMIT_STATUS_CODES = {429, 403, 503}
    RATE_LIMIT_PHRASES = [
        'rate limit', 'too many requests', 'quota exceeded', 
        'temporarily blocked', 'retry after', 'try again later'
    ]
    
    @staticmethod
    def is_rate_limited(response) -> Tuple[bool, Dict]:
        """
        Detect if a response indicates rate limiting.
        
        Returns:
            Tuple: (is_limited, details_dict)
        """
        is_limited = False
        details = {}
        
        # Check status code
        if hasattr(response, 'status_code') and response.status_code in RateLimitDetector.RATE_LIMIT_STATUS_CODES:
            is_limited = True
            details['status_code'] = response.status_code
        
        # Check response headers for rate limit info
        if hasattr(response, 'headers'):
            rate_headers = {k: v for k, v in response.headers.items() if 'rate' in k.lower()}
            if rate_headers:
                details['rate_headers'] = rate_headers
                is_limited = True
                
            # Check for Retry-After header
            if 'retry-after' in response.headers:
                details['retry_after'] = response.headers['retry-after']
                is_limited = True
        
        # Check response content for rate limit phrases
        if hasattr(response, 'text') or hasattr(response, 'content'):
            content = getattr(response, 'text', getattr(response, 'content', ''))
            content_str = str(content).lower()
            
            for phrase in RateLimitDetector.RATE_LIMIT_PHRASES:
                if phrase in content_str:
                    is_limited = True
                    details['matching_phrase'] = phrase
                    break
        
        return is_limited, details


class RateLimitingMiddleware(MiddlewareMixin):
    """Enhanced middleware for managing rate limiting with adaptive proxy rotation."""
    
    def __init__(self, get_response=None):
        super().__init__(get_response)
        
        # Initialize proxy manager
        self.proxy_manager = ProxyManager(countries=["SG"], protocols=["http"], max_proxies=5)
        
        # Track current proxy and request info
        self.current_proxy = None
        self.request_count = 0
        self.start_time = None
        self.last_rotation_time = datetime.now()
        
        # Set initial proxy
        self.set_proxy()
        
        # Configure rate limit tracking
        self.rate_windows = {
            '1min': {'requests': 0, 'window_start': datetime.now(), 'limit': 20},
            '5min': {'requests': 0, 'window_start': datetime.now(), 'limit': 80},
            '15min': {'requests': 0, 'window_start': datetime.now(), 'limit': 200}
        }
        
        # Request throttling settings
        self.min_request_interval = 1.0  # seconds
        self.last_request_time = datetime.now() - timedelta(seconds=self.min_request_interval)
        
        rate_logger.info("RateLimitingMiddleware initialized")
    
    def set_proxy(self) -> bool:
        """Set a working proxy for scholarly and return success status."""
        try:
            best_proxy = self.proxy_manager.get_best_proxy()
            self.current_proxy = best_proxy
            scholarly.use_proxy(self.current_proxy)
            rate_logger.info(f"Set proxy: {self.current_proxy}")
            return True
        except Exception as e:
            rate_logger.error(f"Failed to set proxy: {str(e)}")
            self.current_proxy = None
            return False
    
    def should_throttle(self) -> Tuple[bool, float]:
        """
        Determine if requests should be throttled based on recent rate windows.
        
        Returns:
            Tuple: (should_throttle, recommended_delay)
        """
        now = datetime.now()
        
        # Update window counters
        for window_name, window_data in self.rate_windows.items():
            # Check if window needs reset
            window_duration = int(window_name.replace('min', '')) * 60  # Convert to seconds
            if (now - window_data['window_start']).total_seconds() > window_duration:
                window_data['requests'] = 0
                window_data['window_start'] = now
        
        # Check if any window is approaching its limit (80% capacity)
        for window_name, window_data in self.rate_windows.items():
            limit = window_data['limit']
            current = window_data['requests']
            
            # If we're at 80% or more of the limit, we should throttle
            if current >= limit * 0.8:
                window_duration = int(window_name.replace('min', '')) * 60  # in seconds
                elapsed = (now - window_data['window_start']).total_seconds()
                remaining = window_duration - elapsed
                
                # Calculate a delay that distributes remaining requests over the window
                remaining_requests_allowed = limit - current
                if remaining_requests_allowed <= 0:
                    # We're at limit, delay until window reset
                    recommended_delay = remaining + 1
                else:
                    # Space out remaining allowed requests
                    recommended_delay = max(1.0, remaining / max(1, remaining_requests_allowed))
                    
                rate_logger.debug(
                    f"Throttling: {window_name} window at {current}/{limit} "
                    f"requests ({current/limit:.1%}), recommending {recommended_delay:.2f}s delay"
                )
                
                return True, recommended_delay
        
        # Calculate time since last request
        time_since_last = (now - self.last_request_time).total_seconds()
        
        # If minimum interval hasn't passed, recommend waiting
        if time_since_last < self.min_request_interval:
            return True, self.min_request_interval - time_since_last
            
        return False, 0.0
    
    def update_rate_windows(self) -> None:
        """Update all rate window counters after a successful request."""
        for window in self.rate_windows.values():
            window['requests'] += 1
    
    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """
        Process incoming requests with adaptive rate limiting and proxy rotation.
        Implements throttling and backoff as needed.
        """
        should_throttle, delay = self.should_throttle()
        if should_throttle and delay > 0:
            rate_logger.info(f"Throttling request, sleeping for {delay:.2f}s")
            time.sleep(delay)
        
        self.start_time = time.time()
        self.request_count += 1
        self.last_request_time = datetime.now()
        
        # Track request in rate windows
        self.update_rate_windows()
        
        # Ensure proxy is set
        if not self.current_proxy:
            self.set_proxy()
        
        # Detailed request logging
        rate_logger.info(
            f"Request #{self.request_count} | "
            f"Method: {request.method} | "
            f"Path: {request.path} | "
            f"Proxy: {self.current_proxy}"
        )
        
        # Proxy health check every 20 requests or every 5 minutes
        now = datetime.now()
        if (self.request_count % 20 == 0 or 
            (now - self.last_rotation_time).total_seconds() > 300):
            
            health = self.proxy_manager.get_pool_health()
            rate_logger.info(
                f"Proxy pool health: {health['available_proxies']}/{health['total_proxies']} "
                f"available, {health['total_successes']} successes, "
                f"{health['total_failures']} failures, "
                f"avg response: {health['avg_response_time']:.2f}s"
            )
            
            # Only rotate if we've been using the same proxy for a while
            if (now - self.last_rotation_time).total_seconds() > 300:
                rate_logger.info("Rotating proxy based on time threshold")
                self.set_proxy()
                self.last_rotation_time = now
            
        return None
    
    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """
        Process response to detect rate limiting and track metrics.
        Updates proxy health based on response.
        """
        if not self.start_time or not self.current_proxy:
            return response
            
        response_time = time.time() - self.start_time
        
        # Check for rate limiting in response
        is_rate_limited, details = RateLimitDetector.is_rate_limited(response)
        
        if is_rate_limited:
            rate_logger.warning(
                f"Rate limit detected in response! "
                f"Status: {getattr(response, 'status_code', 'N/A')}. "
                f"Details: {details}"
            )
            
            # Report proxy failure and rotate
            self.proxy_manager.report_failure(self.current_proxy, f"Rate limited: {details}")
            
            # Apply backoff delay if retry-after header is present
            if 'retry_after' in details and details['retry_after'].isdigit():
                retry_after = int(details['retry_after'])
                rate_logger.info(f"Respecting Retry-After header: {retry_after}s")
                time.sleep(retry_after)
                
            # Rotate to a new proxy
            self.set_proxy()
            self.last_rotation_time = datetime.now()
        else:
            # Report successful request
            self.proxy_manager.report_success(self.current_proxy, response_time)
            
            rate_logger.info(
                f"Response: status={getattr(response, 'status_code', 'N/A')}, "
                f"time={response_time:.2f}s, proxy={self.current_proxy}"
            )
        
        return response
    
    def process_exception(self, request: HttpRequest, exception: Exception) -> Optional[HttpResponse]:
        """
        Handle exceptions with adaptive backoff and proxy rotation.
        Classifies exceptions to determine appropriate action.
        """
        error_type = type(exception).__name__
        error_msg = str(exception)
        
        rate_logger.error(
            f"Exception during request: {error_type}: {error_msg} | "
            f"Proxy: {self.current_proxy}"
        )
        
        if self.current_proxy:
            # Report proxy failure
            self.proxy_manager.report_failure(self.current_proxy, error_type)
        
        # Apply progressive backoff based on error type
        if "Timeout" in error_type or "ConnectionError" in error_type:
            # Network errors - short backoff
            backoff = random.uniform(2, 5)
        elif "Forbidden" in error_type or "TooManyRequests" in error_type:
            # Rate limiting errors - longer backoff
            backoff = random.uniform(10, 30)
        else:
            # Other errors - medium backoff
            backoff = random.uniform(5, 15)
            
        rate_logger.info(f"Backing off for {backoff:.2f}s before retry")
        time.sleep(backoff)
        
        # Rotate to a new proxy
        self.set_proxy()
        self.last_rotation_time = datetime.now()
        
        return None