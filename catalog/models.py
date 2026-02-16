from django.db import models
from django.utils.text import slugify
from mptt.models import MPTTModel, TreeForeignKey


class Brand(models.Model):
    name = models.CharField("Название", max_length=200)
    slug = models.SlugField("URL", max_length=200, unique=True, blank=True)
    is_active = models.BooleanField("Активен", default=True)

    class Meta:
        verbose_name = "Бренд"
        verbose_name_plural = "Бренды"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Category(MPTTModel):
    name = models.CharField("Название", max_length=200)
    slug = models.SlugField("URL", max_length=200, unique=True, blank=True)
    parent = TreeForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
        verbose_name="Родитель",
    )
    sort_order = models.PositiveIntegerField("Порядок", default=0)
    is_active = models.BooleanField("Активна", default=True)
    attributes = models.ManyToManyField(
        "ProductAttribute",
        through="CategoryAttribute",
        related_name="categories",
        blank=True,
        verbose_name="Атрибуты категории",
    )

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"
        ordering = ["tree_id", "lft"]

    class MPTTMeta:
        order_insertion_by = ["sort_order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or "category"
            slug = base
            counter = 1
            while Category.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_attribute_ids_with_parents(self):
        ids = set(self.attributes.values_list("id", flat=True))
        for ancestor in self.get_ancestors():
            ids.update(ancestor.attributes.values_list("id", flat=True))
        return ids

    def get_self_and_parents(self):
        return list(self.get_ancestors()) + [self]


class CategoryAttribute(models.Model):
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="category_attributes",
        verbose_name="Категория",
    )
    attribute = models.ForeignKey(
        "ProductAttribute",
        on_delete=models.CASCADE,
        related_name="category_attributes",
        verbose_name="Атрибут",
    )
    is_required = models.BooleanField("Обязателен", default=False)

    class Meta:
        verbose_name = "Атрибут категории"
        verbose_name_plural = "Атрибуты категории"
        unique_together = [["category", "attribute"]]


class ProductAttribute(models.Model):
    name = models.CharField("Название", max_length=100)
    code = models.SlugField("Код", max_length=50, unique=True)

    class Meta:
        verbose_name = "Атрибут товара"
        verbose_name_plural = "Атрибуты товаров"

    def __str__(self):
        return self.name


class ProductAttributeValue(models.Model):
    attribute = models.ForeignKey(
        ProductAttribute,
        on_delete=models.CASCADE,
        related_name="values",
        verbose_name="Атрибут",
    )
    value = models.CharField("Значение", max_length=200)

    class Meta:
        verbose_name = "Значение атрибута"
        verbose_name_plural = "Значения атрибутов"
        unique_together = [["attribute", "value"]]

    def __str__(self):
        return f"{self.attribute.name}: {self.value}"


class Product(models.Model):
    class ProductType(models.TextChoices):
        SIMPLE = "simple", "Простой"
        VARIABLE = "variable", "С вариантами"
        COMPOSITE = "composite", "Составной (бокс)"
        CONFIGURABLE_KIT = "configurable_kit", "Набор-конструктор"
        SERVICE = "service", "Услуга"

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
        verbose_name="Категория",
    )
    brand = models.ForeignKey(
        Brand,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
        verbose_name="Бренд",
    )
    article = models.CharField("Артикул", max_length=100, blank=True, db_index=True)
    name = models.CharField("Название", max_length=500)
    slug = models.SlugField("URL", max_length=500, unique=True, blank=True)
    description = models.TextField("Описание", blank=True)
    product_type = models.CharField(
        "Тип товара",
        max_length=30,
        choices=ProductType.choices,
        default=ProductType.SIMPLE,
    )
    is_active = models.BooleanField("Активен", default=True)
    is_new = models.BooleanField("Новинка", default=False)
    sort_order = models.PositiveIntegerField("Порядок", default=0)
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товары"
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = (slugify(self.name) or "product")[:200]
            slug = base
            counter = 1
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)


class ProductVariant(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="variants",
        verbose_name="Товар",
    )
    price = models.DecimalField(
        "Цена",
        max_digits=12,
        decimal_places=2,
    )
    pv = models.DecimalField(
        "PV",
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Персональный объём (PV) для начисления кешбека.",
    )
    stock = models.PositiveIntegerField("Остаток", default=0)
    is_default = models.BooleanField("По умолчанию", default=False)
    weight_g = models.PositiveIntegerField("Вес (г)", null=True, blank=True)
    length_mm = models.PositiveIntegerField("Длина (мм)", null=True, blank=True)
    width_mm = models.PositiveIntegerField("Ширина (мм)", null=True, blank=True)
    height_mm = models.PositiveIntegerField("Высота (мм)", null=True, blank=True)
    attribute_values = models.ManyToManyField(
        ProductAttributeValue,
        through="ProductVariantAttribute",
        related_name="variants",
        blank=True,
        verbose_name="Характеристики",
    )

    class Meta:
        verbose_name = "Вариант товара"
        verbose_name_plural = "Варианты товаров"

    def __str__(self):
        parts = [self.product.name]
        if self.attribute_values.exists():
            parts.append(
                ", ".join(str(v) for v in self.attribute_values.select_related("attribute"))
            )
        return " — ".join(parts)


class ProductVariantAttribute(models.Model):
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.CASCADE,
        verbose_name="Вариант",
    )
    attribute_value = models.ForeignKey(
        ProductAttributeValue,
        on_delete=models.CASCADE,
        verbose_name="Значение атрибута",
    )

    class Meta:
        verbose_name = "Характеристика варианта"
        verbose_name_plural = "Характеристики вариантов"
        unique_together = [["variant", "attribute_value"]]


class ProductMedia(models.Model):
    class MediaType(models.TextChoices):
        IMAGE = "image", "Изображение"
        VIDEO = "video", "Видео"

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="media",
        verbose_name="Товар",
    )
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="media",
        verbose_name="Вариант",
    )
    file = models.FileField(
        "Файл",
        upload_to="products/%Y/%m/",
    )
    media_type = models.CharField(
        "Тип",
        max_length=10,
        choices=MediaType.choices,
        default=MediaType.IMAGE,
    )
    sort_order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Фото/видео товара"
        verbose_name_plural = "Фото и видео товаров"
        ordering = ["sort_order", "id"]


class CartStorage(models.Model):
    """Корзина в БД — надёжное сохранение вместо сессии."""
    session_key = models.CharField(max_length=40, db_index=True, unique=True)
    data = models.JSONField(default=dict)  # {key: {qty, src} or int}
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Корзина"
        verbose_name_plural = "Корзины"
