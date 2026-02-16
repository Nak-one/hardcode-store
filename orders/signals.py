"""
Сигналы: при создании/изменении/удалении Order ставим запись в очередь выгрузки.
"""
from django.db import transaction
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from .models import Order
from .sync_queue import enqueue_order_sync


@receiver(post_save, sender=Order)
def order_post_save(sender, instance, created, **kwargs):
    if created:
        # Откладываем до коммита транзакции, чтобы в очередь попал заказ уже с позициями (items)
        order_pk = instance.pk

        def enqueue_after_commit():
            order = Order.objects.get(pk=order_pk)
            enqueue_order_sync("create", order)

        transaction.on_commit(enqueue_after_commit)
    else:
        enqueue_order_sync("update", instance)


@receiver(pre_delete, sender=Order)
def order_pre_delete(sender, instance, **kwargs):
    enqueue_order_sync("delete", order=instance)
