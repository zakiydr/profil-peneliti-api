import random
import requests
import logging
from typing import Optional, List
from django.utils.deprecation import MiddlewareMixin
from scholarly import scholarly
from django.http import HttpRequest, HttpResponse

logger = logging.getLogger(__name__)

class ProxyMiddleware(MiddlewareMixin):
    PROXY_API_URL = 'https://api.proxyscrape.com/v4/free-proxy-list/get'
    PROXY_VERIFY_URL = 'http://ipinfo.io/json'
    PROXY_TIMEOUT = 5

    def __init__(self, get_response=None):
        super().__init__(get_response)
        self.proxies: List[str] = []
        self.current_proxy: Optional[str] = None
        self.fetch_proxies()

    def fetch_proxies(self) -> None:
        """Fetch fresh proxies from the API."""
        try:
            params = {
                'request': 'display_proxies',
                'country': 'id',
                'proxy_format': 'protocolipport',
                'format': 'text'
            }
            response = requests.get(self.PROXY_API_URL, params=params, timeout=self.PROXY_TIMEOUT)
            
            if response.status_code == 200:
                self.proxies = [proxy.strip() for proxy in response.text.split('\n') if proxy.strip()]
                logger.info(f"Successfully fetched {len(self.proxies)} proxies")
            else:
                logger.error(f"Failed to fetch proxies. Status code: {response.status_code}")
        
        except requests.RequestException as e:
            logger.error(f"Error fetching proxies: {str(e)}")

    def verify_proxy(self, proxy: str) -> bool:
        """Verify if a proxy is working."""
        try:
            proxy_dict = {'http': f'http://{proxy}', 'https': f'http://{proxy}'}
            response = requests.get(
                self.PROXY_VERIFY_URL,
                proxies=proxy_dict,
                timeout=self.PROXY_TIMEOUT
            )
            return response.status_code == 200
        except requests.RequestException:
            return False

    def set_proxy(self) -> None:
        """Set a working proxy for scholarly."""
        if not self.proxies:
            self.fetch_proxies()
        
        while self.proxies:
            proxy = random.choice(self.proxies)
            if self.verify_proxy(proxy):
                try:
                    scholarly.use_proxy(f'http://{proxy}')
                    self.current_proxy = proxy
                    logger.info(f"Successfully set proxy: {proxy}")
                    return
                except Exception as e:
                    logger.error(f"Failed to set scholarly proxy: {str(e)}")
            
            self.proxies.remove(proxy)
            logger.warning(f"Removed non-working proxy: {proxy}")
        
        logger.warning("No working proxies available")

    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """Process incoming requests and set proxy if needed."""
        if request.method == 'GET' and not self.current_proxy:
            self.set_proxy()
        return None

    def rotate_proxy(self) -> None:
        """Rotate to a new proxy."""
        self.current_proxy = None
        self.set_proxy()
