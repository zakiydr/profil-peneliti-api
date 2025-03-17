# import logging
# from django.utils.deprecation import MiddlewareMixin
# from django.http import HttpRequest, HttpResponse
# from scholarly import scholarly
# from swiftshadow.classes import ProxyInterface
# from typing import Optional


# logger = logging.getLogger(__name__)

# class ProxyMiddleware(MiddlewareMixin):
#     def __init__(self, get_response=None):
#         super().__init__(get_response)
#         # Initialize swiftshadow's ProxyInterface.
#         # Here we filter by country (e.g. "ID" for Indonesia) and protocol ("http").
#         # autoRotate=True automatically switches proxies if one fails.
#         self.proxy_manager = ProxyInterface(countries=["ID"], protocol="http", autoRotate=True)
#         self.current_proxy = None
#         self.set_proxy()

#     def set_proxy(self) -> None:
#         """Set a working proxy for scholarly using swiftshadow."""
#         try:
#             # Get a proxy object and convert it to a string (e.g. "http://<ip>:<port>")
#             proxy_obj = self.proxy_manager.get()
#             self.current_proxy = proxy_obj.as_string()
#             # Set the proxy for scholarly
#             scholarly.use_proxy(self.current_proxy)
#             logger.info(f"Successfully set proxy: {self.current_proxy}")
#         except Exception as e:
#             logger.error(f"Failed to set proxy using swiftshadow: {e}")

#     def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
#         """Process incoming requests and set proxy if not already set."""
#         if request.method == 'GET' and not self.current_proxy:
#             self.set_proxy()
#         return None


#     def rotate_proxy(self) -> None:
#         """Force a proxy rotation by resetting and setting a new proxy."""
#         self.current_proxy = None
#         self.set_proxy()
