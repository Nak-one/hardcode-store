from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.urls import path

from .export_excel import export_pending_to_excel
from .models import User, UserAddress, UserSyncQueue


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("email", "uuid", "is_business_user", "is_staff", "is_active", "referred_by_uuid", "date_joined")
    list_filter = ("is_staff", "is_active", "is_business_user")
    search_fields = ("email", "uuid")
    ordering = ("-date_joined",)
    filter_horizontal = ("groups", "user_permissions")
    readonly_fields = ("uuid", "referred_by_uuid")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Идентификатор", {"fields": ("uuid",)}),
        ("Личные данные", {"fields": ("first_name", "last_name", "username")}),
        ("Приглашение", {"fields": ("referred_by", "referred_by_uuid")}),
        ("Бизнес", {"fields": ("is_business_user",)}),
        (
            "Права",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        ("Важные даты", {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2"),
            },
        ),
    )

    @admin.display(description="Приглашён пользователем (UUID)")
    def referred_by_uuid(self, obj):
        return getattr(obj.referred_by, "uuid", None) or "—"


@admin.register(UserSyncQueue)
class UserSyncQueueAdmin(admin.ModelAdmin):
    list_display = ("id", "action", "user_uuid", "status", "created_at", "sent_at")
    list_filter = ("action", "status")
    search_fields = ("user_uuid", "payload")
    readonly_fields = ("action", "user_uuid", "payload", "created_at")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    change_list_template = "admin/users/usersyncqueue/change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        extra = [
            path(
                "export-excel/",
                staff_member_required(export_pending_to_excel),
                name="users_usersyncqueue_export_excel",
            ),
        ]
        return extra + urls


@admin.register(UserAddress)
class UserAddressAdmin(admin.ModelAdmin):
    list_display = ("user", "city", "address", "is_default")
    list_filter = ("is_default",)
    search_fields = ("user__email", "city", "address")
    raw_id_fields = ("user",)
