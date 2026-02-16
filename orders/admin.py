from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.urls import path
from unfold.admin import ModelAdmin, TabularInline

from .export_excel import export_pending_to_excel
from .models import City, DeliveryMethod, Order, OrderItem, OrderSyncQueue


@admin.register(City)
class CityAdmin(ModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]


@admin.register(DeliveryMethod)
class DeliveryMethodAdmin(ModelAdmin):
    list_display = ["name", "code", "delivery_type", "is_active", "sort_order"]
    list_editable = ["is_active", "sort_order"]


class OrderItemInline(TabularInline):
    model = OrderItem
    extra = 0
    fields = ["variant", "quantity", "price", "pv", "line_total_display", "line_pv_display"]
    readonly_fields = ["variant", "quantity", "price", "pv", "line_total_display", "line_pv_display"]
    can_delete = False

    def line_total_display(self, obj):
        if obj.pk:
            return f"{obj.line_total} ₽"
        return "—"

    line_total_display.short_description = "Сумма"

    def line_pv_display(self, obj):
        if obj.pk:
            return f"{obj.line_pv}"
        return "—"

    line_pv_display.short_description = "PV (итого)"


@admin.register(Order)
class OrderAdmin(ModelAdmin):
    list_display = ["id", "uuid", "number", "name", "email", "phone", "total", "delivery_method", "status", "created_at"]
    list_filter = ["status", "payment_type"]
    list_editable = ["status"]
    search_fields = ["name", "email", "phone"]
    readonly_fields = ["uuid_display", "created_at"]
    date_hierarchy = "created_at"
    inlines = [OrderItemInline]
    fieldsets = (
        ("Идентификатор", {"fields": ("uuid_display", "number")}),
        ("Контактные данные", {"fields": ("name", "email", "phone")}),
        ("Доставка", {"fields": ("delivery_method", "delivery_city", "delivery_address")}),
        ("Оплата и статус", {"fields": ("payment_type", "status", "total", "total_pv")}),
        ("Прочее", {"fields": ("comment", "created_at")}),
    )

    @admin.display(description="GUID")
    def uuid_display(self, obj):
        return str(obj.uuid) if obj and obj.uuid else "—"


@admin.register(OrderSyncQueue)
class OrderSyncQueueAdmin(ModelAdmin):
    list_display = ("id", "action", "order_uuid", "status", "created_at", "sent_at")
    list_filter = ("action", "status")
    search_fields = ("order_uuid", "payload")
    readonly_fields = ("action", "order_uuid", "payload", "created_at")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    change_list_template = "admin/orders/ordersyncqueue/change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        extra = [
            path(
                "export-excel/",
                staff_member_required(export_pending_to_excel),
                name="orders_ordersyncqueue_export_excel",
            ),
        ]
        return extra + urls
