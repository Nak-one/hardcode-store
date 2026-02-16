# Generated manually: OrderSyncQueue

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0004_order_uuid_number"),
    ]

    operations = [
        migrations.CreateModel(
            name="OrderSyncQueue",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "action",
                    models.CharField(
                        choices=[("create", "Создание"), ("update", "Обновление"), ("delete", "Удаление")],
                        db_index=True,
                        max_length=10,
                        verbose_name="Действие",
                    ),
                ),
                ("order_uuid", models.UUIDField(blank=True, db_index=True, null=True, verbose_name="UUID заказа")),
                ("payload", models.JSONField(default=dict, verbose_name="Данные (JSON)")),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "Ожидает выгрузки"), ("sent", "Отправлено"), ("failed", "Ошибка")],
                        db_index=True,
                        default="pending",
                        max_length=10,
                        verbose_name="Статус",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Создано")),
                ("sent_at", models.DateTimeField(blank=True, null=True, verbose_name="Отправлено")),
                ("error_message", models.TextField(blank=True, verbose_name="Ошибка")),
            ],
            options={
                "verbose_name": "Очередь выгрузки заказа",
                "verbose_name_plural": "Очередь выгрузки заказов",
                "ordering": ["-created_at"],
            },
        ),
    ]
