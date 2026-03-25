from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from .models import GlobalIdeia


@receiver(post_save, sender=GlobalIdeia)
@receiver(post_delete, sender=GlobalIdeia)
def invalidar_cache_ideias(sender, **kwargs):
    cache.delete('global_ideias')
