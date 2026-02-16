# Generated manually for User.uuid (GUID v4)

import uuid

from django.db import migrations, models


def generate_uuids_for_users(apps, schema_editor):
    """Заполняет uuid для существующих пользователей."""
    User = apps.get_model("users", "User")
    for user in User.objects.all():
        user.uuid = uuid.uuid4()
        user.save(update_fields=["uuid"])


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0003_user_phone_useraddress"),
    ]

    operations = [
        # 1. Добавляем поле с null=True (для существующих записей)
        migrations.AddField(
            model_name="user",
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
        # 2. Заполняем uuid для всех пользователей
        migrations.RunPython(generate_uuids_for_users, migrations.RunPython.noop),
        # 3. Делаем поле обязательным и добавляем default для новых
        migrations.AlterField(
            model_name="user",
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
    ]
