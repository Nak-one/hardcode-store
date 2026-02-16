import uuid

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    """Manager for email-as-username User."""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email обязателен")
        email = self.normalize_email(email)
        extra_fields.setdefault("username", email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Custom user: email as login, optional referral."""

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    uuid = models.UUIDField(
        "GUID",
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
        help_text="Уникальный идентификатор для интеграций (UUID v4)",
    )
    email = models.EmailField("Email", unique=True)
    username = models.CharField(
        "Username",
        max_length=150,
        blank=True,
        default="",
    )
    referred_by = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="referrals",
        verbose_name="Приглашён пользователем",
    )
    phone = models.CharField("Телефон", max_length=50, blank=True)
    is_business_user = models.BooleanField(
        "Бизнес-пользователь",
        default=False,
        help_text="Пользователь сам включил ведение бизнеса с компанией (отключить сам не может).",
    )

    objects = UserManager()

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"

    def __str__(self):
        return self.email


class UserAddress(models.Model):
    """Сохранённый адрес доставки пользователя."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="addresses",
        verbose_name="Пользователь",
    )
    city = models.CharField("Город", max_length=200)
    address = models.TextField("Адрес (улица, дом, квартира)")
    postal_code = models.CharField("Индекс", max_length=20, blank=True)
    is_default = models.BooleanField("По умолчанию", default=False)

    class Meta:
        verbose_name = "Адрес доставки"
        verbose_name_plural = "Адреса доставки"
        ordering = ["-is_default", "id"]

    def __str__(self):
        return f"{self.city}, {self.address[:50]}"


class UserSyncQueue(models.Model):
    """
    Очередь выгрузки изменений пользователей в другие сервисы.
    Заполняется при создании, изменении и удалении User.
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
    user_uuid = models.UUIDField(
        "UUID пользователя",
        null=True,
        blank=True,
        db_index=True,
        help_text="Для delete может быть только в payload после удаления из БД.",
    )
    payload = models.JSONField(
        "Данные (JSON)",
        default=dict,
        help_text="Данные для выгрузки: uuid, email, is_business_user, referred_by_uuid и т.д.",
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
        verbose_name = "Очередь выгрузки пользователя"
        verbose_name_plural = "Очередь выгрузки пользователей"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_action_display()} {self.user_uuid or '—'} ({self.get_status_display()})"
