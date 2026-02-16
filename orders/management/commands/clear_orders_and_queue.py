"""
Удаляет все заказы (OrderItem, Order) и очищает очередь OrderSyncQueue.
"""
from django.core.management.base import BaseCommand

from orders.models import Order, OrderItem, OrderSyncQueue


class Command(BaseCommand):
    help = "Удалить все заказы и очистить очередь OrderSyncQueue."

    def handle(self, *args, **options):
        items_deleted, _ = OrderItem.objects.all().delete()
        orders_deleted, _ = Order.objects.all().delete()
        queue_deleted, _ = OrderSyncQueue.objects.all().delete()
        self.stdout.write(
            self.style.SUCCESS(
                f"Удалено: {orders_deleted} заказов, {items_deleted} позиций, {queue_deleted} записей в очереди."
            )
        )
