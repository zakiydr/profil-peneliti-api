from django.db import models

# Create your models here.
from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    google_id = models.CharField(max_length=255, blank=True, null=True)
    profile_picture = models.URLField(blank=True, null=True)
    
    def __str__(self):
        return self.email