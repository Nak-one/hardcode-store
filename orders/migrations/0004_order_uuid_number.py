# Generated manually: uuid, number for Order

import uuid

from django.db import migrations, models


def populate_uuid_and_number(apps, schema_editor):
    Order = apps.get_model("orders", "Order")
    start = 100000
    for i, order in enumerate(Order.objects.order_by("id")):
        order.uuid = uuid.uuid4()
        order.number = start + i
        order.save(update_fields=["uuid", "number"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0003_alter_order_user_fk_to_users"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="uuid",
            field=models.UUIDField(
                db_index=True,
                editable=False,
                help_text="Уникальный идентификатор для интеграций (UUID v4)",
                null=True,
                unique=True,
                verbose_name="GUID",
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="number",
            field=models.PositiveIntegerField(
                db_index=True,
                help_text="Человекочитаемый номер (с 100000)",
                null=True,
                unique=True,
                verbose_name="Номер заказа",
            ),
        ),
        migrations.RunPython(populate_uuid_and_number, noop),
        migrations.AlterField(
            model_name="order",
            name="uuid",
            field=models.UUIDField(
                db_index=True,
                default=uuid.uuid4,
                editable=False,
                help_text="Уникальный идентификатор для интеграций (UUID v4)",
                unique=True,
                verbose_name="GUID",
            ),
        ),
        migrations.AlterField(
            model_name="order",
            name="number",
            field=models.PositiveIntegerField(
                db_index=True,
                help_text="Человекочитаемый номер (с 100000)",
                null=True,
                unique=True,
                verbose_name="Номер заказа",
            ),
        ),
    ]
