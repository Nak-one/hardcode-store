import itertools

from django import forms
from django.contrib import admin
from django.http import HttpRequest, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from django.contrib.admin.widgets import RelatedFieldWidgetWrapper
from mptt.admin import MPTTModelAdmin
from mptt.forms import TreeNodeChoiceField
from unfold.admin import ModelAdmin, TabularInline, StackedInline
from unfold.widgets import INPUT_CLASSES, LABEL_CLASSES

from .models import (
    Brand,
    Category,
    CategoryAttribute,
    Product,
    ProductAttribute,
    ProductAttributeValue,
    ProductMedia,
    ProductVariant,
    ProductVariantAttribute,
)


@admin.register(Brand)
class BrandAdmin(ModelAdmin):
    list_display = ["name", "slug", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}
    fieldsets = (
        ("Основное", {"fields": ("name", "slug")}),
        ("Статус", {"fields": ("is_active",)}),
    )


class CategoryAttributeInline(TabularInline):
    model = CategoryAttribute
    extra = 0
    fields = ["attribute", "is_required"]
    autocomplete_fields = ["attribute"]


@admin.register(Category)
class CategoryAdmin(MPTTModelAdmin):
    list_display = ["tree_title", "slug", "sort_order", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}
    list_editable = ["sort_order", "is_active"]
    inlines = [CategoryAttributeInline]
    mptt_level_indent = 20
    list_display_links = ["tree_title"]
    change_list_template = "admin/catalog/category/change_list.html"
    fieldsets = (
        ("Основное", {"fields": ("name", "slug", "parent")}),
        ("Статус и сортировка", {"fields": ("is_active", "sort_order")}),
    )

    def tree_title(self, obj):
        indent = obj.level * 18
        return format_html(
            '<span style="display:inline-block;padding-left:{}px;">{}</span>',
            indent,
            obj.name,
        )

    tree_title.short_description = "Категория (дерево)"

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "parent":
            kwargs["form_class"] = TreeNodeChoiceField
            kwargs["empty_label"] = "— корневая категория —"
        formfield = super().formfield_for_foreignkey(db_field, request, **kwargs)
        if db_field.name == "parent" and isinstance(formfield.widget, RelatedFieldWidgetWrapper):
            formfield.widget.can_add_related = False
            formfield.widget.can_change_related = False
            formfield.widget.can_delete_related = False
            formfield.widget.can_view_related = False
            formfield.help_text = "Выбери родительскую категорию или оставь пустым для корневой."
        return formfield


class ProductAttributeValueInline(TabularInline):
    model = ProductAttributeValue
    extra = 1


@admin.register(ProductAttributeValue)
class ProductAttributeValueAdmin(ModelAdmin):
    list_display = ["attribute", "value"]
    list_filter = ["attribute"]
    search_fields = ["value", "attribute__name"]
    autocomplete_fields = ["attribute"]
    fieldsets = (("Основное", {"fields": ("attribute", "value")}),)


@admin.register(ProductAttribute)
class ProductAttributeAdmin(ModelAdmin):
    list_display = ["name", "code"]
    search_fields = ["name", "code"]
    inlines = [ProductAttributeValueInline]
    fieldsets = (("Основное", {"fields": ("name", "code")}),)


class ProductMediaInline(TabularInline):
    model = ProductMedia
    extra = 1
    fields = ["file", "media_type", "sort_order"]


@admin.register(Product)
class ProductAdmin(ModelAdmin):
    list_display = ["name", "article", "category", "brand", "product_type", "is_active", "is_new", "sort_order"]
    list_filter = ["product_type", "is_active", "category", "brand"]
    search_fields = ["name", "article"]
    prepopulated_fields = {"slug": ("name",)}
    list_editable = ["is_active", "is_new", "sort_order"]
    inlines = [ProductMediaInline]
    autocomplete_fields = ["category", "brand"]
    actions = ["generate_variants"]

    class Media:
        css = {"all": ["admin/custom.css"]}

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:product_id>/generate-variants/",
                self.admin_site.admin_view(self.generate_variants_view),
                name="catalog_product_generate_variants",
            ),
        ]
        return custom_urls + urls

    def generate_variants(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Выбери один товар для генерации вариантов.", level="warning")
            return
        product = queryset.first()
        url = reverse("admin:catalog_product_generate_variants", args=[product.pk])
        return HttpResponseRedirect(url)

    generate_variants.short_description = "Сгенерировать варианты (цвет/размер)"

    def generate_variants_view(self, request: HttpRequest, product_id: int):
        product = Product.objects.filter(pk=product_id).first()
        if not product:
            self.message_user(request, "Товар не найден.", level="error")
            return HttpResponseRedirect(reverse("admin:catalog_product_changelist"))

        allowed_attrs = []
        if product.category:
            allowed_ids = product.category.get_attribute_ids_with_parents()
            if allowed_ids:
                allowed_attrs = list(
                    ProductAttribute.objects.filter(id__in=allowed_ids).order_by("name")
                )

        class VariantsGeneratorForm(forms.Form):
            price = forms.DecimalField(label="Цена", max_digits=12, decimal_places=2)
            stock = forms.IntegerField(label="Остаток", min_value=0, initial=0)
            weight_g = forms.IntegerField(label="Вес (г)", min_value=0, required=False)
            length_mm = forms.IntegerField(label="Длина (мм)", min_value=0, required=False)
            width_mm = forms.IntegerField(label="Ширина (мм)", min_value=0, required=False)
            height_mm = forms.IntegerField(label="Высота (мм)", min_value=0, required=False)

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                for name in [
                    "price",
                    "stock",
                    "weight_g",
                    "length_mm",
                    "width_mm",
                    "height_mm",
                ]:
                    self.fields[name].widget.attrs.update(
                        {"class": " ".join(INPUT_CLASSES)}
                    )
                for attr in allowed_attrs:
                    values = ProductAttributeValue.objects.filter(attribute=attr).order_by("value")
                    self.fields[f"attr_{attr.id}"] = forms.ModelMultipleChoiceField(
                        queryset=values,
                        required=False,
                        label=f"{attr.name}",
                        widget=forms.CheckboxSelectMultiple,
                    )
                    self.fields[f"attr_{attr.id}"].widget.attrs.update(
                        {"class": "space-y-2"}
                    )

        form = VariantsGeneratorForm(request.POST or None)
        if request.method == "POST" and form.is_valid():
            selected_groups = []
            for attr in allowed_attrs:
                values = form.cleaned_data.get(f"attr_{attr.id}")
                if values:
                    selected_groups.append(list(values))

            if not selected_groups:
                form.add_error(None, "Выбери хотя бы одну характеристику (например, Цвет и/или Размер).")
            else:
                existing = set()
                for variant in product.variants.all().prefetch_related("attribute_values"):
                    key = tuple(sorted(v.id for v in variant.attribute_values.all()))
                    existing.add(key)

                created = 0
                price = form.cleaned_data["price"]
                stock = form.cleaned_data["stock"]
                for combo in itertools.product(*selected_groups):
                    key = tuple(sorted(v.id for v in combo))
                    if key in existing:
                        continue

                    variant = ProductVariant.objects.create(
                        product=product,
                        price=price,
                        stock=stock,
                        is_default=False,
                        weight_g=form.cleaned_data.get("weight_g"),
                        length_mm=form.cleaned_data.get("length_mm"),
                        width_mm=form.cleaned_data.get("width_mm"),
                        height_mm=form.cleaned_data.get("height_mm"),
                    )
                    variant.attribute_values.set(combo)
                    created += 1

                self.message_user(request, f"Создано вариантов: {created}")
                return HttpResponseRedirect(reverse("admin:catalog_product_change", args=[product.pk]))

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "product": product,
            "form": form,
            "allowed_attrs_count": len(allowed_attrs),
            "title": "Генерация вариантов",
        }
        return TemplateResponse(request, "admin/catalog/product/generate_variants.html", context)

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        extra_context = extra_context or {}
        if object_id:
            product = self.get_object(request, object_id)
            if product:
                variants = product.variants.prefetch_related("attribute_values__attribute").order_by("id")
                extra_context.update(
                    {
                        "variants": variants,
                        "variants_list_url": (
                            reverse("admin:catalog_productvariant_changelist")
                            + f"?product__id__exact={product.pk}"
                        ),
                        "variant_add_url": (
                            reverse("admin:catalog_productvariant_add")
                            + f"?product={product.pk}"
                        ),
                        "variants_generate_url": reverse(
                            "admin:catalog_product_generate_variants", args=[product.pk]
                        ),
                    }
                )
        return super().changeform_view(request, object_id, form_url, extra_context)


class ProductVariantAttributeInline(TabularInline):
    model = ProductVariantAttribute
    extra = 1
    autocomplete_fields = ["attribute_value"]


@admin.register(ProductVariant)
class ProductVariantAdmin(ModelAdmin):
    list_display = ["product", "price", "pv", "stock", "is_default", "weight_g"]
    list_filter = ["is_default"]
    search_fields = ["product__name"]
    autocomplete_fields = ["product"]
    inlines = [ProductVariantAttributeInline]
    save_as = True

    actions = ["duplicate_variants"]

    def duplicate_variants(self, request, queryset):
        created = 0
        for variant in queryset:
            attrs = list(variant.attribute_values.all())
            variant.pk = None
            variant.is_default = False
            variant.save()
            variant.attribute_values.set(attrs)
            created += 1
        self.message_user(request, f"Создано копий: {created}")

    duplicate_variants.short_description = "Скопировать варианты"


@admin.register(ProductMedia)
class ProductMediaAdmin(ModelAdmin):
    list_display = ["product", "media_type", "sort_order", "preview"]
    list_filter = ["media_type"]
    search_fields = ["product__name"]
    autocomplete_fields = ["product", "variant"]

    def preview(self, obj):
        if obj.media_type == "image" and obj.file:
            return format_html('<img src="{}" style="max-height: 50px;" />', obj.file.url)
        return "—"

    preview.short_description = "Превью"
