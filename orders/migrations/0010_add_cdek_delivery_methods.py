# Generated migration: способы доставки ТК СДЭК

from django.db import migrations


def add_cdek_methods(apps, schema_editor):
    DeliveryMethod = apps.get_model("orders", "DeliveryMethod")
    DeliveryMethod.objects.get_or_create(
        code="cdek_courier",
        defaults={"name": "СДЭК Курьер", "delivery_type": "courier", "is_active": True, "sort_order": 10},
    )
    DeliveryMethod.objects.get_or_create(
        code="cdek_pvz",
        defaults={"name": "СДЭК ПВЗ", "delivery_type": "pvz", "is_active": True, "sort_order": 11},
    )


def remove_cdek_methods(apps, schema_editor):
    DeliveryMethod = apps.get_model("orders", "DeliveryMethod")
    DeliveryMethod.objects.filter(code__in=["cdek_courier", "cdek_pvz"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0009_add_cdek_order_fields"),
    ]

    operations = [
        migrations.RunPython(add_cdek_methods, remove_cdek_methods),
    ]
