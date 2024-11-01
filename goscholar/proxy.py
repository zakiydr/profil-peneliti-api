import time
from scholarly import ProxyGenerator
from fp.fp import FreeProxy
from scholarly import scholarly

def set_proxy():
    while True:
        attempt = 0
        max_attempts = 3
        
        while attempt <= max_attempts:
            try:
                pg = ProxyGenerator()
                proxy = FreeProxy(rand=True, timeout=5).get()
                proxy_setup = pg.SingleProxy(http=proxy, https=proxy)
                if proxy_setup:
                    print(f"Sucessfully set proxy: {proxy}")
                    return proxy
                attempt += 1
                time.sleep(1)
            except Exception as e:
                print(F"Proxy setup failed: {str(e)}")
                attempt += 1
                time.sleep(1)
        
        print("All attempts failed, starting...")
        time.sleep(2)
        # print(f"Successfully set proxy: {proxy}")
        # return proxy