"""
Команда для добавления розовой футболки MONOCHROME I ❤️ MOSCOW.
"""
from django.core.management.base import BaseCommand
from catalog.models import (
    Category, Brand, Product, ProductVariant,
    ProductAttribute, ProductAttributeValue, ProductMedia,
)


class Command(BaseCommand):
    help = "Добавить розовую футболку MONOCHROME M/XL"

    def handle(self, *args, **options):
        category = Category.objects.get(slug="cat-3")
        brand, _ = Brand.objects.get_or_create(
            name="MONOCHROME",
            defaults={"slug": "monochrome"},
        )
        if brand.slug != "monochrome":
            brand.slug = "monochrome"
            brand.save(update_fields=["slug"])

        size_attr = ProductAttribute.objects.get(code="size")
        size_m = ProductAttributeValue.objects.get(attribute=size_attr, value="M")
        size_xl = ProductAttributeValue.objects.get(attribute=size_attr, value="XL")

        color_attr = ProductAttribute.objects.get(code="color")
        color_pink, _ = ProductAttributeValue.objects.get_or_create(
            attribute=color_attr, value="Розовый"
        )

        product, created = Product.objects.get_or_create(
            slug="futbolka-monochrome-i-love-moscow-pink",
            defaults={
                "category": category,
                "brand": brand,
                "name": "Футболка MONOCHROME I ❤️ MOSCOW",
                "description": "Футболка розового цвета с принтом MONOCHROME™ I ❤️ MOSCOW. Хлопок, свободный крой.",
                "product_type": Product.ProductType.VARIABLE,
                "is_active": True,
                "is_new": True,
            },
        )
        if created:
            self.stdout.write(f"Создан товар: {product.name}")
        else:
            self.stdout.write(f"Товар уже существует: {product.name}")

        for size_val, stock in [(size_m, 10), (size_xl, 8)]:
            existing = product.variants.filter(
                attribute_values=size_val
            ).filter(attribute_values=color_pink).first()
            if existing:
                existing.stock = stock
                existing.save(update_fields=["stock"])
                self.stdout.write(f"  Вариант {size_val.value}: обновлён")
            else:
                v = ProductVariant.objects.create(
                    product=product,
                    price=1990,
                    stock=stock,
                    is_default=(size_val.value == "M"),
                )
                v.attribute_values.set([size_val, color_pink])
                self.stdout.write(f"  Вариант {size_val.value}: создан")

        images = [
            ("products/2026/01/futbolka-monochrome-pink-01.png", 0),
            ("products/2026/01/futbolka-monochrome-pink-02.png", 1),
        ]
        for path, order in images:
            if not ProductMedia.objects.filter(product=product, file=path).exists():
                ProductMedia.objects.create(
                    product=product,
                    file=path,
                    media_type="image",
                    sort_order=order,
                )
                self.stdout.write(f"  Изображение: {path}")

        self.stdout.write(self.style.SUCCESS("Готово."))
