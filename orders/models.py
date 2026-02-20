import uuid

from django.conf import settings
from django.db import models, transaction


class DeliveryMethod(models.Model):
    class DeliveryType(models.TextChoices):
        PVZ = "pvz", "ПВЗ (пункт выдачи)"
        COURIER = "courier", "Курьер"
        PICKUP = "pickup", "Самовывоз"

    name = models.CharField("Название", max_length=200)
    code = models.SlugField("Код", max_length=50, unique=True)
    delivery_type = models.CharField(
        "Тип",
        max_length=20,
        choices=DeliveryType.choices,
        default=DeliveryType.COURIER,
    )
    is_active = models.BooleanField("Активен", default=True)
    sort_order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Способ доставки"
        verbose_name_plural = "Способы доставки"
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


def _get_next_order_number():
    """Возвращает следующий номер заказа (начиная с 100000)."""
    with transaction.atomic():
        last = Order.objects.select_for_update().aggregate(
            mx=models.Max("number")
        )["mx"]
        return (last or 99999) + 1


class Order(models.Model):
    class PaymentType(models.TextChoices):
        CASH = "cash", "При получении"
        ONLINE = "online", "Онлайн"

    class Status(models.TextChoices):
        NEW = "new", "Новый"
        PAID = "paid", "Оплачен"
        SHIPPED = "shipped", "Передан в доставку"
        DELIVERED = "delivered", "Доставлен"
        CANCELLED = "cancelled", "Отменён"

    uuid = models.UUIDField(
        "GUID",
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
        help_text="Уникальный идентификатор для интеграций (UUID v4)",
    )
    number = models.PositiveIntegerField(
        "Номер заказа",
        unique=True,
        db_index=True,
        null=True,
        blank=True,
        help_text="Человекочитаемый номер (с 100000)",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
        verbose_name="Пользователь",
    )
    name = models.CharField("Имя", max_length=200)
    email = models.EmailField("Email")
    phone = models.CharField("Телефон", max_length=50)
    delivery_method = models.ForeignKey(
        DeliveryMethod,
        on_delete=models.PROTECT,
        related_name="orders",
        verbose_name="Способ доставки",
    )
    delivery_city = models.CharField("Город", max_length=200, blank=True)
    delivery_address = models.TextField("Адрес доставки / ПВЗ", blank=True)
    # СДЭК: код города и ПВЗ для доставки в пункт выдачи
    cdek_city_code = models.PositiveIntegerField("Код города СДЭК", null=True, blank=True)
    cdek_pvz_code = models.CharField("Код ПВЗ СДЭК", max_length=100, blank=True)
    # 5post: UUID пункта выдачи (для доставки в постамат/ПВЗ)
    fivepost_pvz_id = models.CharField("Код ПВЗ 5post (UUID)", max_length=64, blank=True)
    # Почта России: индекс получателя (6 цифр) для доставки
    russianpost_to_index = models.CharField("Индекс получателя (Почта России)", max_length=6, blank=True)
    delivery_cost = models.DecimalField(
        "Стоимость доставки",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    payment_type = models.CharField(
        "Способ оплаты",
        max_length=20,
        choices=PaymentType.choices,
        default=PaymentType.CASH,
    )
    total = models.DecimalField(
        "Сумма заказа",
        max_digits=12,
        decimal_places=2,
        default=0,
    )
    total_pv = models.DecimalField(
        "PV заказа",
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Итоговый персональный объём (PV) по заказу.",
    )
    status = models.CharField(
        "Статус",
        max_length=20,
        choices=Status.choices,
        default=Status.NEW,
        db_index=True,
    )
    comment = models.TextField("Комментарий", blank=True)
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if self.pk is None and self.number is None:
            self.number = _get_next_order_number()
        super().save(*args, **kwargs)

    def __str__(self):
        num = self.number or self.pk
        return f"Заказ #{num} от {self.created_at.strftime('%d.%m.%Y')}"


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="Заказ",
    )
    variant = models.ForeignKey(
        "catalog.ProductVariant",
        on_delete=models.PROTECT,
        related_name="order_items",
        verbose_name="Вариант товара",
    )
    quantity = models.PositiveIntegerField("Количество", default=1)
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
        help_text="PV позиции на момент покупки (снимок из варианта товара).",
    )

    class Meta:
        verbose_name = "Позиция заказа"
        verbose_name_plural = "Позиции заказа"

    def __str__(self):
        return f"{self.variant} × {self.quantity}"

    @property
    def line_total(self):
        return self.price * self.quantity

    @property
    def line_pv(self):
        return self.pv * self.quantity


class OrderSyncQueue(models.Model):
    """
    Очередь выгрузки изменений заказов в другие сервисы.
    Заполняется при создании, изменении и удалении Order.
    """

    class Action(models.TextChoices):
        CREATE = "create", "Создание"
        UPDATE = "update", "Обновление"
        DELETE = "delete", "Удаление"

    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает выгрузки"
        SENT = "sent", "Отправлено"
        FAILED = "failed", "Ошибка"

    action = models.CharField(
        "Действие",
        max_length=10,
        choices=Action.choices,
        db_index=True,
    )
    order_uuid = models.UUIDField(
        "UUID заказа",
        null=True,
        blank=True,
        db_index=True,
    )
    payload = models.JSONField(
        "Данные (JSON)",
        default=dict,
    )
    status = models.CharField(
        "Статус",
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField("Создано", auto_now_add=True, db_index=True)
    sent_at = models.DateTimeField("Отправлено", null=True, blank=True)
    error_message = models.TextField("Ошибка", blank=True)

    class Meta:
        verbose_name = "Очередь выгрузки заказа"
        verbose_name_plural = "Очередь выгрузки заказов"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_action_display()} {self.order_uuid or '-'} ({self.get_status_display()})"


class City(models.Model):
    """Каталог городов для подстановки при оформлении доставки."""
    name = models.CharField("Название", max_length=200, unique=True)

    class Meta:
        verbose_name = "Город"
        verbose_name_plural = "Города"
        ordering = ["name"]

    def __str__(self):
        return self.name
