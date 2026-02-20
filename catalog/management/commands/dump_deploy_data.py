"""
Выгрузка контента для переноса на другой сервер (без заказов и пользователей).

Создаёт JSON-фикстуру: каталог (бренды, категории, атрибуты, товары, варианты, медиа),
справочник городов и пользователей (users.User, UserAddress). Заказы и корзины не включаются.

Использование:
  python manage.py dump_deploy_data
  python manage.py dump_deploy_data -o deploy_data/fixture.json

На новом месте:
  python manage.py migrate
  python manage.py loaddata deploy_data/fixture.json
"""
import os
from django.core.management import call_command
from django.core.management.base import BaseCommand


# Порядок важен: от зависимостей к зависимым
DEPLOY_DATA_APPS = [
    "catalog.ProductAttribute",
    "catalog.ProductAttributeValue",
    "catalog.Brand",
    "catalog.Category",
    "catalog.CategoryAttribute",
    "catalog.Product",
    "catalog.ProductVariant",
    "catalog.ProductVariantAttribute",
    "catalog.ProductMedia",
    "orders.City",
    "users.User",
    "users.UserAddress",
]


class Command(BaseCommand):
    help = "Выгрузить каталог и города в JSON для переноса (без заказов и пользователей)"

    def add_arguments(self, parser):
        parser.add_argument(
            "-o", "--output",
            default="deploy_data/fixture.json",
            help="Путь к выходному JSON-файлу (по умолчанию deploy_data/fixture.json)",
        )

    def handle(self, *args, **options):
        out_path = options["output"]
        out_dir = os.path.dirname(out_path)
        if out_dir and not os.path.isdir(out_dir):
            os.makedirs(out_dir, exist_ok=True)
            self.stdout.write(f"Создана папка: {out_dir}")

        with open(out_path, "w", encoding="utf-8") as f:
            call_command(
                "dumpdata",
                *DEPLOY_DATA_APPS,
                indent=2,
                stdout=f,
            )

        self.stdout.write(self.style.SUCCESS(f"Фикстура записана: {out_path}"))
        self.stdout.write("На новом месте: migrate → loaddata " + out_path)
        if out_path.startswith("deploy_data/"):
            self.stdout.write("Медиа-файлы (изображения товаров) скопируйте в MEDIA_ROOT вручную или архивом.")
