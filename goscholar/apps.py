from django.apps import AppConfig


class GoscholarConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "goscholar"
    
    # def ready(self):
    #     """
    #     Initialize the app and set up the proxy rotation system.
    #     """
    #     # Import the proxy rotator to ensure it's loaded
    #     from .proxy_rotator import proxy_rotator
        
    #     # Initialize the proxy list
    #     proxy_rotator.refresh_proxy_list()