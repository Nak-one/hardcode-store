"""
Сигналы: при создании/изменении/удалении User ставим запись в очередь выгрузки.
"""
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from .models import User
from .sync_queue import enqueue_user_sync


@receiver(post_save, sender=User)
def user_post_save(sender, instance, created, **kwargs):
    if created:
        enqueue_user_sync("create", instance)
    else:
        enqueue_user_sync("update", instance)


@receiver(pre_delete, sender=User)
def user_pre_delete(sender, instance, **kwargs):
    enqueue_user_sync("delete", user=instance)
