"""
Создаёт N заказов от имени админа, как при оформлении с сайта.
События создания попадают в OrderSyncQueue (сигналы post_save).
При нехватке остатков у вариантов — увеличивает остатки.
"""
import time
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from orders.models import DeliveryMethod, Order, OrderItem
from catalog.models import ProductVariant


class Command(BaseCommand):
    help = "Создать N заказов на админа (как с сайта), при необходимости добавить остатки."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=1000, help="Количество заказов (по умолчанию 1000)")

    def handle(self, *args, **options):
        count = max(1, options.get("count", 1000))
        from django.contrib.auth import get_user_model
        User = get_user_model()

        admin = User.objects.filter(is_superuser=True).first()
        if not admin:
            self.stderr.write("Нет суперпользователя. Создайте: python manage.py createsuperuser")
            return

        dm = DeliveryMethod.objects.filter(is_active=True, delivery_type="courier").first()
        if not dm:
            dm = DeliveryMethod.objects.filter(is_active=True).first()
        if not dm:
            self.stderr.write("Нет активного способа доставки в БД.")
            return

        variants = list(
            ProductVariant.objects.select_related("product")
            .filter(product__is_active=True)
            .order_by("product_id", "pk")[:50]
        )
        if not variants:
            self.stderr.write("Нет вариантов товаров в каталоге.")
            return

        # Обеспечиваем остатки: на N заказов при круглой ротации ~ N/len(variants), плюс 2-й товар у 1/3 заказов
        min_stock = max(5, ((count * 4) // (3 * len(variants))) + 100)
        updated = 0
        for v in variants:
            if v.stock < min_stock:
                v.stock = min_stock
                v.save(update_fields=["stock"])
                updated += 1
        if updated:
            self.stdout.write(f"Остатки выставлены до {min_stock} у {updated} вариантов.")

        t0 = time.perf_counter()
        name = admin.get_full_name() or admin.email
        email = admin.email
        phone = getattr(admin, "phone", None) or "+7 900 000-00-00"
        delivery_city = "Москва"
        delivery_address = "ул. Примерная, д. 1, кв. 1"
        payment_type = Order.PaymentType.CASH
        comment = "Тестовый заказ (management command)"

        created_count = 0
        for i in range(count):
            # По 1–2 позиции в заказе, разные варианты
            v1 = variants[i % len(variants)]
            qty1 = 1
            if v1.stock < qty1:
                self.stdout.write(f"Пропуск заказа: у варианта {v1.pk} нет остатка.")
                continue
            line_total = v1.price * qty1
            total_pv = (getattr(v1, "pv", 0) or Decimal("0")) * qty1
            second_v = None
            if len(variants) > 1 and (i % 3) == 0:
                idx2 = (i + 1) % len(variants)
                v2 = variants[idx2]
                if v2.pk != v1.pk and v2.stock >= 1:
                    second_v = (v2, 1)
                    line_total += v2.price
                    total_pv += (getattr(v2, "pv", 0) or Decimal("0")) * 1

            with transaction.atomic():
                order = Order.objects.create(
                    user=admin,
                    name=name,
                    email=email,
                    phone=phone,
                    delivery_method=dm,
                    delivery_city=delivery_city,
                    delivery_address=delivery_address,
                    payment_type=payment_type,
                    total=line_total,
                    total_pv=total_pv,
                    status=Order.Status.NEW,
                    comment=comment,
                )
                OrderItem.objects.create(
                    order=order,
                    variant=v1,
                    quantity=qty1,
                    price=v1.price,
                    pv=getattr(v1, "pv", 0) or Decimal("0"),
                )
                v1.stock -= qty1
                v1.save(update_fields=["stock"])

                if second_v:
                    v2, qty2 = second_v
                    OrderItem.objects.create(
                        order=order,
                        variant=v2,
                        quantity=qty2,
                        price=v2.price,
                        pv=getattr(v2, "pv", 0) or Decimal("0"),
                    )
                    v2.stock -= qty2
                    v2.save(update_fields=["stock"])

            created_count += 1
            if created_count <= 5 or created_count % 200 == 0 or created_count == count:
                self.stdout.write(f"Создан заказ #{order.number} ({created_count}/{count})")

        elapsed = time.perf_counter() - t0
        self.stdout.write(
            self.style.SUCCESS(
                f"Готово: создано заказов {created_count} за {elapsed:.1f} с "
                f"(~{elapsed / max(1, created_count) * 1000:.0f} мс на заказ). События в очереди OrderSyncQueue."
            )
        )
