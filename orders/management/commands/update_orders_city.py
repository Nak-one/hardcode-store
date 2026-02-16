"""
Обновляет delivery_city у первых N заказов (по id), чтобы в очереди OrderSyncQueue
появились события UPDATE.
"""
from django.core.management.base import BaseCommand

from orders.models import Order


CITIES = ("Москва", "Санкт-Петербург", "Новосибирск", "Екатеринбург", "Казань")


class Command(BaseCommand):
    help = "Изменить город доставки у N заказов (по умолчанию 1000), чтобы в очереди появились обновления."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=1000, help="Количество заказов для обновления")

    def handle(self, *args, **options):
        count = max(1, options.get("count", 1000))
        orders = list(Order.objects.order_by("id")[:count])
        if not orders:
            self.stdout.write("Нет заказов для обновления.")
            return
        updated = 0
        for i, order in enumerate(orders):
            new_city = CITIES[i % len(CITIES)]
            if order.delivery_city != new_city:
                order.delivery_city = new_city
                order.save(update_fields=["delivery_city"])
                updated += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"Обновлено заказов: {updated}. В очереди OrderSyncQueue добавлены записи UPDATE."
            )
        )
