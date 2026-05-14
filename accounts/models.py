from django.db import models

# Create your models here.
# Create your models here.
class TrackedDevice(models.Model):
    user_id = models.CharField(max_length=255)
    device_info = models.JSONField()
