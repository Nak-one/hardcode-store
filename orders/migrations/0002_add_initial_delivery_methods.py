from django.db import migrations


def add_initial_delivery_methods(apps, schema_editor):
    DeliveryMethod = apps.get_model("orders", "DeliveryMethod")
    DeliveryMethod.objects.bulk_create([
        DeliveryMethod(name="Самовывоз", code="pickup", delivery_type="pickup", sort_order=0),
        DeliveryMethod(name="Курьер", code="courier", delivery_type="courier", sort_order=1),
        DeliveryMethod(name="ПВЗ (пункт выдачи)", code="pvz", delivery_type="pvz", sort_order=2),
    ])


def remove_initial_delivery_methods(apps, schema_editor):
    DeliveryMethod = apps.get_model("orders", "DeliveryMethod")
    DeliveryMethod.objects.filter(code__in=["pickup", "courier", "pvz"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0001_initial_order_models"),
    ]

    operations = [
        migrations.RunPython(add_initial_delivery_methods, remove_initial_delivery_methods),
    ]
