# 5post: поле ПВЗ в заказе

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0011_fivepost_delivery_methods"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="fivepost_pvz_id",
            field=models.CharField(blank=True, max_length=64, verbose_name="Код ПВЗ 5post (UUID)"),
        ),
    ]
