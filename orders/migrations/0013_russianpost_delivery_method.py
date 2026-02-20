# Почта России: способ доставки

from django.db import migrations


def add_russianpost_method(apps, schema_editor):
    DeliveryMethod = apps.get_model("orders", "DeliveryMethod")
    DeliveryMethod.objects.get_or_create(
        code="russianpost",
        defaults={"name": "Почта России", "delivery_type": "courier", "is_active": True, "sort_order": 30},
    )


def remove_russianpost_method(apps, schema_editor):
    DeliveryMethod = apps.get_model("orders", "DeliveryMethod")
    DeliveryMethod.objects.filter(code="russianpost").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0012_order_fivepost_pvz_id"),
    ]

    operations = [
        migrations.RunPython(add_russianpost_method, remove_russianpost_method),
    ]
