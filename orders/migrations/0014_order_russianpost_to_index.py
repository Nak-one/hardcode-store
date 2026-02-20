# Почта России: индекс получателя в заказе

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0013_russianpost_delivery_method"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="russianpost_to_index",
            field=models.CharField(blank=True, max_length=6, verbose_name="Индекс получателя (Почта России)"),
        ),
    ]
