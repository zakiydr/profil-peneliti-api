import logging
from django.utils.deprecation import MiddlewareMixin
from django.http import HttpRequest, HttpResponse
from scholarly import scholarly
from swiftshadow.classes import ProxyInterface

logger = logging.getLogger(__name__)

class SwiftshadowProxyMiddleware(MiddlewareMixin):
    """
    Django middleware for robust proxy rotation using swiftshadow.
    This middleware integrates with the scholarly library by setting a working proxy,
    and rotates proxies on exceptions or on responses indicating blocking.
    """
    def __init__(self, get_response=None):
        super().__init__(get_response)
        try:
            # Initialize the proxy manager.
            # You can adjust filters (e.g. country and protocol) as needed.
            self.proxy_manager = ProxyInterface(countries=["ID"], protocol="http", autoRotate=True)
            self.current_proxy = None
            self.set_proxy()
        except Exception as e:
            logger.error(f"Failed to initialize ProxyInterface: {e}")
            self.proxy_manager = None

    def set_proxy(self) -> None:
        """
        Retrieve a new proxy from swiftshadow and configure scholarly to use it.
        Note: We pass the proxy object directly (instead of its string representation)
        so that scholarly can call get_session() on it.
        """
        if self.proxy_manager is None:
            logger.error("Proxy manager is not available.")
            return

        try:
            # Get a validated proxy object.
            proxy_obj = self.proxy_manager.get()
            # Store the proxy object rather than its string.
            self.current_proxy = proxy_obj
            # Set the proxy for scholarly by passing the proxy object.
            scholarly.use_proxy(proxy_obj)
            logger.info(f"Using new proxy: {proxy_obj.as_string()}")
        except Exception as e:
            logger.error(f"Error setting proxy: {e}")
            self.current_proxy = None

    def rotate_proxy(self) -> None:
        """
        Force a rotation by clearing the current proxy and fetching a new one.
        """
        logger.info("Rotating proxy...")
        self.current_proxy = None
        self.set_proxy()

    def process_request(self, request: HttpRequest) -> HttpResponse:
        """
        Ensure that a proxy is set before processing the request.
        """
        if not self.current_proxy:
            self.set_proxy()
        return None

    def process_exception(self, request: HttpRequest, exception: Exception) -> HttpResponse:
        """
        On encountering an exception during request processing, rotate the proxy.
        """
        logger.warning(f"Exception encountered: {exception}. Rotating proxy.")
        self.rotate_proxy()
        # Let other middleware or the view handle the exception.
        return None

    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """
        Optionally rotate the proxy if the response status code indicates potential blocking.
        """
        if response.status_code in [403, 429, 502, 503]:
            logger.warning(f"Response status {response.status_code} indicates a block. Rotating proxy.")
            self.rotate_proxy()
        return response
