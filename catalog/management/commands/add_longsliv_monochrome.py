"""
Добавить лонгслив MONOCHROME розовый (M, XL).
"""
from django.core.management.base import BaseCommand
from catalog.models import (
    Category, Brand, Product, ProductVariant,
    ProductAttribute, ProductAttributeValue, ProductMedia,
)


class Command(BaseCommand):
    help = "Добавить лонгслив MONOCHROME розовый M/XL"

    def handle(self, *args, **options):
        category = Category.objects.get(slug="cat-3")
        brand = Brand.objects.get(slug="monochrome")

        size_attr = ProductAttribute.objects.get(code="size")
        size_m = ProductAttributeValue.objects.get(attribute=size_attr, value="M")
        size_xl = ProductAttributeValue.objects.get(attribute=size_attr, value="XL")
        color_pink = ProductAttributeValue.objects.get(
            attribute=ProductAttribute.objects.get(code="color"),
            value="Розовый",
        )

        product, created = Product.objects.get_or_create(
            slug="longsliv-monochrome-rozovyy",
            defaults={
                "category": category,
                "brand": brand,
                "name": "Лонгслив MONOCHROME розовый",
                "description": "Лонгслив с принтом MONOCHROME®. Розово-белый мраморный принт, свободный крой, длинные рукава.",
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
                ProductVariant.objects.create(
                    product=product,
                    price=2490,
                    stock=stock,
                    is_default=(size_val.value == "M"),
                ).attribute_values.set([size_val, color_pink])
                self.stdout.write(f"  Вариант {size_val.value}: создан")

        path = "products/2026/01/longsliv-monochrome-pink-01.png"
        if not ProductMedia.objects.filter(product=product, file=path).exists():
            ProductMedia.objects.create(
                product=product,
                file=path,
                media_type="image",
                sort_order=0,
            )
            self.stdout.write(f"  Изображение: {path}")

        self.stdout.write(self.style.SUCCESS("Готово."))
