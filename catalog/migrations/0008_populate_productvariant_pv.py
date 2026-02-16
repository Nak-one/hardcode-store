# Generated manually: populate PV from price

from decimal import Decimal, ROUND_HALF_UP

from django.db import migrations


def populate_pv(apps, schema_editor):
    ProductVariant = apps.get_model("catalog", "ProductVariant")

    rate = Decimal("120")  # 1 PV ~= 120₽

    for v in ProductVariant.objects.all().only("id", "price", "pv"):
        price = v.price or Decimal("0")
        if price <= 0:
            new_pv = Decimal("0")
        else:
            approx = (price / rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            new_pv = approx if approx >= 1 else Decimal("1")

        if v.pv != new_pv:
            v.pv = new_pv
            v.save(update_fields=["pv"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0007_productvariant_pv"),
    ]

    operations = [
        migrations.RunPython(populate_pv, noop),
    ]

