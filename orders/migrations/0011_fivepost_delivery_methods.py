# 5post: способы доставки (курьер и ПВЗ)

from django.db import migrations


def add_fivepost_methods(apps, schema_editor):
    DeliveryMethod = apps.get_model("orders", "DeliveryMethod")
    DeliveryMethod.objects.get_or_create(
        code="fivepost_courier",
        defaults={"name": "5post Курьер", "delivery_type": "courier", "is_active": True, "sort_order": 20},
    )
    DeliveryMethod.objects.get_or_create(
        code="fivepost_pvz",
        defaults={"name": "5post ПВЗ", "delivery_type": "pvz", "is_active": True, "sort_order": 21},
    )


def remove_fivepost_methods(apps, schema_editor):
    DeliveryMethod = apps.get_model("orders", "DeliveryMethod")
    DeliveryMethod.objects.filter(code__in=["fivepost_courier", "fivepost_pvz"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0010_add_cdek_delivery_methods"),
    ]

    operations = [
        migrations.RunPython(add_fivepost_methods, remove_fivepost_methods),
    ]
