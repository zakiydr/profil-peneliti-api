# """
# Django management command to test and validate proxies.
# """
# import time
# from typing import List, Tuple

# from django.core.management.base import BaseCommand

# from goscholar.proxy_rotator import ProxyListDownloader, proxy_rotator


# class Command(BaseCommand):
#     help = "Test and validate proxies from the proxy list"
    
#     def add_arguments(self, parser):
#         parser.add_argument(
#             "--limit", 
#             type=int, 
#             default=10,
#             help="Number of proxies to test"
#         )
#         parser.add_argument(
#             "--type", 
#             type=str, 
#             choices=["http", "socks4", "socks5", "all"],
#             default="all",
#             help="Type of proxies to test"
#         )
        
#     def handle(self, *args, **options):
#         limit = options["limit"]
#         proxy_type = None if options["type"] == "all" else options["type"]
        
#         self.stdout.write(self.style.SUCCESS(f"Testing up to {limit} proxies of type '{options['type']}'"))
        
#         # Download fresh proxy list
#         proxy_rotator.refresh_proxy_list()
        
#         # Get available proxies
#         proxies = proxy_rotator.get_available_proxies(proxy_type)
        
#         if not proxies:
#             self.stdout.write(self.style.ERROR(f"No proxies of type '{options['type']}' available"))
#             return
            
#         # Limit number of proxies to test
#         proxies_to_test = proxies[:limit]
        
#         # Test proxies
#         results = []
#         for i, proxy in enumerate(proxies_to_test, 1):
#             self.stdout.write(f"Testing proxy {i}/{len(proxies_to_test)}: {proxy}")
#             start_time = time.time()
#             success = proxy_rotator.configure_scholarly_with_proxy(proxy)
#             elapsed = time.time() - start_time
            
#             results.append((proxy, success, elapsed))
            
#             if success:
#                 self.stdout.write(self.style.SUCCESS(f"  ✓ Success in {elapsed:.2f}s"))
#             else:
#                 self.stdout.write(self.style.ERROR(f"  ✗ Failed in {elapsed:.2f}s"))
                
#         # Print summary
#         successful = [r for r in results if r[1]]
#         self.stdout.write("\nSummary:")
#         self.stdout.write(f"Total tested: {len(results)}")
#         self.stdout.write(self.style.SUCCESS(f"Successful: {len(successful)}"))
#         self.stdout.write(self.style.ERROR(f"Failed: {len(results) - len(successful)}"))
        
#         if successful:
#             self.stdout.write("\nSuccessful proxies:")
#             for proxy, _, elapsed in successful:
#                 self.stdout.write(f"  {proxy} ({elapsed:.2f}s)")