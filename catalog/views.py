import uuid
from decimal import Decimal

from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.template.loader import render_to_string

from .models import Category, Product, ProductVariant
from .cart_storage import get_cart, set_cart
from . import cart_logic as cl
from .cart_log import log


def _cart_build_item(cart_key, item):
    """
    По ключу и item {p, v, q} строит данные для шаблона.
    Возвращает dict или None.
    """
    product_id = item.get("p")
    variant_id = item.get("v")
    qty = max(1, int(item.get("q", 1)))
    if not product_id:
        return None
    try:
        product = Product.objects.prefetch_related(
            "variants", "media", "variants__attribute_values__attribute"
        ).get(pk=product_id, is_active=True)
    except Product.DoesNotExist:
        return None
    variants = list(product.variants.prefetch_related("attribute_values__attribute").all())
    has_variants = len(variants) > 1

    if variant_id is None:
        variant = product.variants.first()
    else:
        try:
            variant = ProductVariant.objects.select_related("product").prefetch_related(
                "product__media", "attribute_values__attribute"
            ).get(pk=variant_id, product=product)
        except (ProductVariant.DoesNotExist, ValueError):
            return None
    if not variant or variant.stock < qty:
        return None

    line_total = variant.price * qty
    pv = getattr(variant, "pv", Decimal("0")) or Decimal("0")
    line_pv = pv * qty
    img = product.media.filter(media_type="image").first()
    variants_flat = [
        {"pk": v.pk, "label": ", ".join(f"{av.attribute.name}: {av.value}" for av in v.attribute_values.select_related("attribute").all())}
        for v in variants if v.stock > 0
    ]

    return {
        "variant": variant,
        "qty": qty,
        "line_total": line_total,
        "pv": pv,
        "line_pv": line_pv,
        "image": img,
        "has_variants": has_variants,
        "variants_flat": variants_flat,
        "cart_key": cart_key,
        "needs_selection": variant_id is None and has_variants,
    }


def _product_cart_qty(cart, product_id):
    n = 0
    for item in cart.values():
        if item.get("p") == product_id:
            n += item.get("q", 1)
    return n


def _variant_cart_qty(cart, product_id, variant_id):
    """Количество в корзине для конкретного варианта."""
    n = 0
    vid = int(variant_id) if variant_id is not None else None
    for item in cart.values():
        if item.get("p") == product_id and item.get("v") == vid:
            n += item.get("q", 1)
    return n


def product_list(request, category_slug=None):
    from django.db.models import Count, Subquery, OuterRef
    from django.http import HttpResponseRedirect
    from django.urls import reverse

    q = request.GET.get("q", "").strip()
    if not q and "q" in request.GET:
        return HttpResponseRedirect(reverse("catalog:product_list"))

    products = Product.objects.filter(
        is_active=True
    ).exclude(slug__isnull=True).exclude(slug="").select_related("category", "brand")

    product_count_subq = Product.objects.filter(
        is_active=True,
        category__tree_id=OuterRef('tree_id'),
        category__lft__gte=OuterRef('lft'),
        category__rght__lte=OuterRef('rght'),
    ).values('category__tree_id').annotate(c=Count('id')).values('c')[:1]

    categories = Category.objects.filter(
        parent__isnull=True, is_active=True
    ).exclude(slug__isnull=True).exclude(slug="").annotate(
        product_count=Subquery(product_count_subq)
    ).filter(product_count__gt=0)

    if q:
        products = products.filter(name__icontains=q)
    filter_new = request.GET.get("new") == "1"
    if filter_new:
        products = products.filter(is_new=True)
    if category_slug:
        cat = get_object_or_404(Category, slug=category_slug, is_active=True)
    else:
        cat = None

    new_count = Product.objects.filter(is_active=True, is_new=True).exclude(slug__isnull=True).exclude(slug="").count() if not q else 0
    products = products.prefetch_related("variants", "media")
    cart = get_cart(request)
    favorites_ids = set(_get_favorites(request))
    for p in products:
        p.root_category_slug = p.category.get_root().slug if p.category else ""
        p.default_variant = p.variants.filter(is_default=True).first() or p.variants.first()
        p.main_image = p.media.filter(media_type="image").first()
        p.variants_list = list(p.variants.all())
        p.cart_qty = _product_cart_qty(cart, p.pk)
        p.is_in_favorites = p.pk in favorites_ids

    recent_ids = _get_recent_viewed(request, limit=6)
    recent_products = []
    if recent_ids:
        recent_products = list(
            Product.objects.filter(pk__in=recent_ids, is_active=True)
            .exclude(slug__isnull=True).exclude(slug="")
            .select_related("category", "brand").prefetch_related("variants", "media")
        )
        order_map = {pid: i for i, pid in enumerate(recent_ids)}
        recent_products.sort(key=lambda p: order_map.get(p.pk, 999))
        for p in recent_products:
            p.root_category_slug = p.category.get_root().slug if p.category else ""
            p.default_variant = p.variants.filter(is_default=True).first() or p.variants.first()
            p.main_image = p.media.filter(media_type="image").first()
            p.variants_list = list(p.variants.all())
            p.cart_qty = _product_cart_qty(cart, p.pk)
            p.is_in_favorites = p.pk in favorites_ids

    return render(request, "catalog/product_list.html", {
        "products": products,
        "categories": categories,
        "current_category": cat,
        "recent_products": recent_products,
        "filter_new": filter_new,
        "new_count": new_count,
    })


def product_detail(request, slug):
    import json
    product = get_object_or_404(Product, slug=slug, is_active=True)
    variants = list(product.variants.prefetch_related("attribute_values__attribute").all())
    product.variants_list = variants
    def_v = product.variants.filter(is_default=True).first() or product.variants.first()
    if def_v and def_v.stock < 1:
        def_v = next((v for v in variants if v.stock > 0), def_v)
    product.default_variant = def_v
    product.images_list = product.media.filter(media_type="image").order_by("sort_order")

    variant_stock = {v.pk: v.stock for v in variants}
    attrs = {}
    for v in variants:
        for av in v.attribute_values.all():
            attr_name = av.attribute.name
            if attr_name not in attrs:
                attrs[attr_name] = {}
            if av.value not in attrs[attr_name]:
                attrs[attr_name][av.value] = []
            attrs[attr_name][av.value].append(v.pk)
    product.variants_by_attr = []
    for name, vals in attrs.items():
        def_val = None
        if def_v:
            for av in def_v.attribute_values.all():
                if av.attribute.name == name:
                    def_val = av.value
                    break
        fallback_default = next(
            (val for val, ids in vals.items() if any(variant_stock.get(i, 0) > 0 for i in ids)),
            def_val,
        )
        if def_val not in vals or not any(variant_stock.get(i, 0) > 0 for i in vals.get(def_val, [])):
            def_val = fallback_default
        out_vals = []
        for val, ids in vals.items():
            has_stock = any(variant_stock.get(i, 0) > 0 for i in ids)
            out_vals.append({
                "value": val,
                "variant_ids": ",".join(str(i) for i in ids),
                "is_default": def_val == val and has_stock,
                "has_stock": has_stock,
            })
        product.variants_by_attr.append({"name": name, "values": out_vals})
    cart = get_cart(request)
    product.variants_json = json.dumps({
        str(v.pk): {
            "price": str(v.price),
            "pv": str(getattr(v, "pv", 0) or 0),
            "label": ", ".join(av.value for av in v.attribute_values.select_related("attribute").order_by("attribute__name")) or str(v),
            "cart_qty": _variant_cart_qty(cart, product.pk, v.pk),
        }
        for v in variants
    })
    def_v = product.default_variant
    product.initial_variant_cart_qty = _variant_cart_qty(cart, product.pk, def_v.pk) if def_v else 0
    product.default_variant_label = (
        ", ".join(av.value for av in def_v.attribute_values.select_related("attribute").order_by("attribute__name"))
        if def_v and def_v.attribute_values.exists() else (str(def_v) if def_v else "")
    )
    product.is_in_favorites = product.pk in _get_favorites(request)
    _add_recent_viewed(request, product.pk)
    recent_ids = _get_recent_viewed(request, exclude=product.pk, limit=4)
    recent_products = list(
        Product.objects.filter(pk__in=recent_ids, is_active=True)
        .exclude(slug__isnull=True).exclude(slug="")
        .select_related("category", "brand").prefetch_related("variants", "media")
    )
    order_map = {pid: i for i, pid in enumerate(recent_ids)}
    recent_products.sort(key=lambda p: order_map.get(p.pk, 999))
    for p in recent_products:
        p.root_category_slug = p.category.get_root().slug if p.category else ""
        p.default_variant = p.variants.filter(is_default=True).first() or p.variants.first()
        p.main_image = p.media.filter(media_type="image").first()
        p.variants_list = list(p.variants.all())
        p.cart_qty = _product_cart_qty(get_cart(request), p.pk)
        p.is_in_favorites = p.pk in _get_favorites(request)
    related_products = []
    if product.category_id:
        rq = Product.objects.filter(category=product.category, is_active=True).exclude(pk=product.pk).exclude(slug__isnull=True).exclude(slug="")
        related_products = list(rq.select_related("category", "brand").prefetch_related("variants", "media")[:6])
        rc, rf = get_cart(request), _get_favorites(request)
        for p in related_products:
            p.root_category_slug = p.category.get_root().slug if p.category else ""
            p.default_variant = p.variants.filter(is_default=True).first() or p.variants.first()
            p.main_image = p.media.filter(media_type="image").first()
            p.variants_list = list(p.variants.all())
            p.cart_qty = _product_cart_qty(rc, p.pk)
            p.is_in_favorites = p.pk in rf
    return render(request, "catalog/product_detail.html", {
        "product": product,
        "recent_products": recent_products,
        "related_products": related_products,
    })


def product_quick_view(request, slug):
    """Возвращает HTML фрагмент для модального окна быстрого просмотра."""
    import json
    product = get_object_or_404(Product, slug=slug, is_active=True)
    variants = list(product.variants.prefetch_related("attribute_values__attribute").all())
    product.variants_list = variants
    def_v = product.variants.filter(is_default=True).first() or product.variants.first()
    if def_v and def_v.stock < 1:
        def_v = next((v for v in variants if v.stock > 0), def_v)
    product.default_variant = def_v
    product.images_list = product.media.filter(media_type="image").order_by("sort_order")

    variant_stock = {v.pk: v.stock for v in variants}
    attrs = {}
    for v in variants:
        for av in v.attribute_values.all():
            attr_name = av.attribute.name
            if attr_name not in attrs:
                attrs[attr_name] = {}
            if av.value not in attrs[attr_name]:
                attrs[attr_name][av.value] = []
            attrs[attr_name][av.value].append(v.pk)
    product.variants_by_attr = []
    for name, vals in attrs.items():
        def_val = None
        if def_v:
            for av in def_v.attribute_values.all():
                if av.attribute.name == name:
                    def_val = av.value
                    break
        fallback_default = next(
            (val for val, ids in vals.items() if any(variant_stock.get(i, 0) > 0 for i in ids)),
            def_val,
        )
        if def_val not in vals or not any(variant_stock.get(i, 0) > 0 for i in vals.get(def_val, [])):
            def_val = fallback_default
        out_vals = []
        for val, ids in vals.items():
            has_stock = any(variant_stock.get(i, 0) > 0 for i in ids)
            out_vals.append({
                "value": val,
                "variant_ids": ",".join(str(i) for i in ids),
                "is_default": def_val == val and has_stock,
                "has_stock": has_stock,
            })
        product.variants_by_attr.append({"name": name, "values": out_vals})
    product.variants_json = json.dumps({str(v.pk): {"price": str(v.price)} for v in variants})
    cart = get_cart(request)
    product.cart_qty = _product_cart_qty(cart, product.pk)
    return render(request, "catalog/product_quick_view.html", {"product": product})


def _cart_items_list(cart):
    """По корзине строит список item dict для шаблона."""
    items = []
    total = Decimal("0")
    total_pv = Decimal("0")
    for key, item in cart.items():
        data = _cart_build_item(key, item)
        if data is None:
            continue
        items.append(data)
        total += data["line_total"]
        total_pv += data.get("line_pv") or Decimal("0")
    return items, total, total_pv


def _cart_weight_grams(cart):
    """Суммарный вес корзины в граммах (для калькулятора СДЭК). По умолчанию 500 г на позицию."""
    total = 0
    for key, item in cart.items():
        data = _cart_build_item(key, item)
        if data is None:
            continue
        v = data["variant"]
        qty = data["qty"]
        w = getattr(v, "weight_g", None)
        if w is None or w <= 0:
            w = 500
        total += int(w) * qty
    return max(500, total)


def _render_cart(request, cart=None):
    if cart is None:
        cart = get_cart(request)
    items, total, total_pv = _cart_items_list(cart)
    log.info("[_render_cart] cart_keys=%s items_count=%s needs_selection=%s",
             list(cart.keys()), len(items),
             [i.get("cart_key") for i in items if i.get("needs_selection")])
    resp = render(request, "catalog/cart.html", {"cart_items": items, "total": total, "total_pv": total_pv})
    resp["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp["Pragma"] = "no-cache"
    return resp


def cart_view(request):
    log.info("[cart_view] GET cart page")
    return _render_cart(request)


@require_POST
def cart_add(request):
    variant_id = request.POST.get("variant_id")
    qty = int(request.POST.get("qty", 1))
    source = request.POST.get("source", "catalog")
    if source not in ("catalog", "detail"):
        source = "catalog"
    if qty < 1:
        qty = 1

    try:
        v = ProductVariant.objects.select_related("product").prefetch_related("product__variants").get(pk=variant_id)
    except (ProductVariant.DoesNotExist, ValueError):
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "error": "Вариант не найден"}, status=400)
        return redirect("catalog:product_list")

    has_variants = v.product.variants.count() > 1
    if has_variants and source == "catalog":
        qty = 1
    if v.stock < qty:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "error": "Недостаточно на складе"}, status=400)
        return redirect("catalog:product_detail", slug=v.product.slug)

    cart = get_cart(request)
    log.info("[cart_add] product_id=%s variant_id=%s source=%s has_variants=%s cart_keys_before=%s",
             v.product_id, v.pk, source, has_variants, list(cart.keys()))
    if source == "detail":
        cart = cl.add_from_detail(cart, v.product_id, v.pk, qty, has_variants=has_variants)
    else:
        cart = cl.add_from_catalog(cart, v.product_id, v.pk, qty, has_variants=has_variants)
    set_cart(request, cart)

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({
            "ok": True,
            "count": cl.cart_total_count(cart),
            "cart_qty": _product_cart_qty(cart, v.product_id),
            "variant_qty": _variant_cart_qty(cart, v.product_id, v.pk),
        })
    return redirect("catalog:cart")


@require_POST
def cart_remove_last(request):
    product_id = request.POST.get("product_id")
    variant_id = request.POST.get("variant_id")
    try:
        product_id = int(product_id)
    except (TypeError, ValueError):
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "error": "Неверные данные"}, status=400)
        return redirect("catalog:product_list")
    if not Product.objects.filter(pk=product_id).exists():
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "error": "Товар не найден"}, status=400)
        return redirect("catalog:product_list")

    cart = get_cart(request)
    if variant_id:
        try:
            cart = cl.remove_last_for_variant(cart, product_id, int(variant_id))
        except (TypeError, ValueError):
            cart = cl.remove_last_for_product(cart, product_id)
    else:
        cart = cl.remove_last_for_product(cart, product_id)
    set_cart(request, cart)

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({
            "ok": True,
            "count": cl.cart_total_count(cart),
            "cart_qty": _product_cart_qty(cart, product_id),
            "variant_qty": _variant_cart_qty(cart, product_id, variant_id) if variant_id else _product_cart_qty(cart, product_id),
        })
    return redirect("catalog:cart")


@require_POST
def cart_remove(request):
    item_id = request.POST.get("cart_key") or request.POST.get("item_id")
    if not item_id:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "error": "Не указана позиция"}, status=400)
        return redirect("catalog:cart")

    cart = get_cart(request)
    cart = cl.remove_item(cart, str(item_id))
    set_cart(request, cart)

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "count": cl.cart_total_count(cart)})
    return redirect("catalog:cart")


@require_POST
def cart_set(request):
    cart_key = request.POST.get("cart_key") or request.POST.get("item_id")
    variant_id = request.POST.get("variant_id")
    product_id = request.POST.get("product_id")
    qty = int(request.POST.get("qty", 0))
    if qty < 0:
        qty = 0
    cart = get_cart(request)
    if cart_key:
        cart = cl.set_qty(cart, str(cart_key), qty)
    elif variant_id and product_id:
        try:
            cart = cl.set_qty_by_variant(cart, int(product_id), variant_id, qty)
        except (TypeError, ValueError):
            cart = None
    else:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "error": "Не указана позиция"}, status=400)
        return redirect("catalog:cart")
    if cart is None:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "error": "Позиция не найдена"}, status=400)
        return redirect("catalog:cart")
    set_cart(request, cart)

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "count": cl.cart_total_count(cart), "qty": qty})
    return redirect("catalog:cart")


@require_POST
def cart_replace(request):
    """Применить выбранную характеристику к плейсхолдеру в корзине."""
    item_id = (request.POST.get("old_key") or request.GET.get("old_key") or request.POST.get("cart_key") or "").strip()
    new_variant_id = (request.POST.get("new_variant_id") or "").strip()
    log.info("[cart_replace] POST=%s GET=%s -> item_id=%r new_variant_id=%r",
             dict(request.POST), dict(request.GET), item_id, new_variant_id)
    if not item_id or not new_variant_id:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "error": "Неверные данные"}, status=400)
        return redirect("catalog:cart")

    try:
        new_v = ProductVariant.objects.select_related("product").get(pk=new_variant_id)
        if new_v.stock < 1:
            log.warning("[cart_replace] variant %s stock=0", new_variant_id)
            from django.contrib import messages
            messages.error(request, "Выбранный вариант недоступен (нет в наличии). Выберите другой.")
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"ok": False, "error": "Недостаточно на складе"}, status=400)
            return redirect("catalog:cart")
    except (ProductVariant.DoesNotExist, ValueError) as e:
        log.warning("[cart_replace] variant %s not found or invalid: %s", new_variant_id, e)
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "error": "Вариант не найден"}, status=400)
        return redirect("catalog:cart")

    cart = get_cart(request)
    log.info("[cart_replace] cart before replace keys=%s", list(cart.keys()))
    cart = cl.replace_variant(cart, str(item_id), new_variant_id)
    if cart is None:
        log.warning("[cart_replace] replace_variant returned None -> redirect")
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "error": "Позиция не найдена"}, status=400)
        return redirect("catalog:cart")

    set_cart(request, cart)
    log.info("[cart_replace] set_cart done, returning response")

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        items, total, total_pv = _cart_items_list(cart)
        row_html = ""
        for it in items:
            if it["cart_key"] == item_id:
                row_html = render_to_string("catalog/cart_item_row.html", {"item": it}, request=request)
                break
        total_str = f"{total:.2f}".replace(".", ",") + " ₽"
        total_pv_str = f"{total_pv:.2f}".replace(".", ",") + " PV"
        return JsonResponse({
            "ok": True,
            "count": cl.cart_total_count(cart),
            "cart_key": item_id,
            "row_html": row_html,
            "total": total_str,
            "total_pv": total_pv_str,
        })
    return _render_cart(request, cart)


def checkout_view(request):
    """Оформление заказа — одна страница, три этапа (корзина → доставка → оплата)."""
    from django.views.decorators.http import require_http_methods
    from orders.models import DeliveryMethod

    cart = get_cart(request)
    items, total, total_pv = _cart_items_list(cart)

    if not items:
        from django.contrib import messages
        messages.info(request, "Корзина пуста. Добавьте товары для оформления заказа.")
        return redirect("catalog:cart")

    needs_selection = any(i.get("needs_selection") for i in items)
    if needs_selection:
        from django.contrib import messages
        messages.warning(request, "Укажите характеристики для всех товаров перед оформлением.")
        return redirect("catalog:cart")

    # ТК: СДЭК, 5post, Почта России
    delivery_methods = list(
        DeliveryMethod.objects.filter(
            is_active=True,
            code__in=["cdek_courier", "cdek_pvz", "fivepost_courier", "fivepost_pvz", "russianpost"],
        ).order_by("sort_order", "name")
    )

    if request.method == "POST":
        return _checkout_post(request, items, total, delivery_methods)

    # Подстановка данных пользователя и сохранённых адресов
    checkout_name = checkout_email = checkout_phone = ""
    checkout_delivery_city = checkout_delivery_address = ""
    user_addresses = []
    if request.user.is_authenticated:
        u = request.user
        checkout_name = " ".join(filter(None, [u.first_name, u.last_name])).strip() or u.email
        checkout_email = u.email or ""
        checkout_phone = u.phone or ""
        user_addresses = list(u.addresses.all())
        default_addr = next((a for a in user_addresses if a.is_default), user_addresses[0] if user_addresses else None)
        if default_addr:
            checkout_delivery_city = default_addr.city or ""
            checkout_delivery_address = default_addr.address or ""

    cart = get_cart(request)
    cart_weight_grams = _cart_weight_grams(cart)
    return render(request, "catalog/checkout.html", {
        "cart_items": items,
        "total": total,
        "total_pv": total_pv,
        "cart_weight_grams": cart_weight_grams,
        "delivery_methods": delivery_methods,
        "checkout_name": checkout_name,
        "checkout_email": checkout_email,
        "checkout_phone": checkout_phone,
        "checkout_delivery_city": checkout_delivery_city,
        "checkout_delivery_address": checkout_delivery_address,
        "user_addresses": user_addresses,
    })


def _checkout_post(request, items, total, delivery_methods):
    """Обработка POST: валидация и создание заказа."""
    from django.contrib import messages
    from orders.models import Order, OrderItem, DeliveryMethod

    name = (request.POST.get("name") or "").strip()
    email = (request.POST.get("email") or "").strip()
    phone = (request.POST.get("phone") or "").strip()
    delivery_method_id = request.POST.get("delivery_method")
    delivery_city = (request.POST.get("delivery_city") or "").strip()
    delivery_address = (request.POST.get("delivery_address") or "").strip()
    cdek_city_code = request.POST.get("cdek_city_code")
    cdek_pvz_code = (request.POST.get("cdek_pvz_code") or "").strip()
    fivepost_pvz_id = (request.POST.get("fivepost_pvz_id") or "").strip()
    russianpost_to_index = (request.POST.get("russianpost_to_index") or "").strip().replace(" ", "")
    delivery_cost_raw = request.POST.get("delivery_cost")
    payment_type = request.POST.get("payment_type") or "cash"
    comment = (request.POST.get("comment") or "").strip()

    errors = []
    if not name:
        errors.append("Укажите имя.")
    if not email:
        errors.append("Укажите email.")
    elif "@" not in email:
        errors.append("Некорректный email.")
    if not phone:
        errors.append("Укажите телефон.")

    try:
        dm = (
            DeliveryMethod.objects.filter(
                is_active=True,
                code__in=["cdek_courier", "cdek_pvz", "fivepost_courier", "fivepost_pvz", "russianpost"],
            ).get(pk=delivery_method_id)
        )
    except (DeliveryMethod.DoesNotExist, ValueError, TypeError):
        dm = None
    if not dm:
        errors.append("Выберите способ доставки.")

    if dm:
        if not delivery_city:
            errors.append("Укажите город.")
        if dm.delivery_type == "pvz" and dm.code.startswith("cdek_") and not cdek_pvz_code:
            errors.append("Выберите пункт выдачи СДЭК.")
        if dm.delivery_type == "pvz" and dm.code.startswith("fivepost_") and not fivepost_pvz_id:
            errors.append("Выберите пункт выдачи 5post.")
        if dm.code == "russianpost":
            if len(russianpost_to_index) != 6 or not russianpost_to_index.isdigit():
                errors.append("Укажите 6-значный индекс доставки (Почта России).")
        if not delivery_address:
            errors.append("Укажите адрес доставки или выберите пункт выдачи.")

    if payment_type not in ("cash", "online"):
        payment_type = "cash"

    if errors:
        for e in errors:
            messages.error(request, e)
        user_addresses = []
        if request.user.is_authenticated:
            user_addresses = list(request.user.addresses.all())
        cart = get_cart(request)
        return render(request, "catalog/checkout.html", {
            "cart_items": items,
            "total": total,
            "total_pv": sum((i.get("line_pv") or Decimal("0")) for i in items),
            "cart_weight_grams": _cart_weight_grams(cart),
            "delivery_methods": delivery_methods,
            "checkout_name": name,
            "checkout_email": email,
            "checkout_phone": phone,
            "checkout_delivery_method_id": delivery_method_id,
            "checkout_delivery_city": delivery_city,
            "checkout_delivery_address": delivery_address,
            "checkout_payment_type": payment_type,
            "checkout_comment": comment,
            "user_addresses": user_addresses,
        })

    try:
        with _checkout_lock():
            cart = get_cart(request)
            items, total, _ = _cart_items_list(cart)
            if not items:
                messages.error(request, "Корзина пуста. Добавьте товары.")
                return redirect("catalog:cart")

            from django.db import transaction as db_transaction

            # Считаем итоговый PV до создания заказа, чтобы не делать лишний save() и не плодить событие update
            total_pv = 0
            for item in items:
                v = item["variant"]
                qty = item["qty"]
                total_pv += (getattr(v, "pv", 0) or 0) * qty

            cdek_code = int(cdek_city_code) if cdek_city_code and str(cdek_city_code).isdigit() else None
            try:
                delivery_cost_val = Decimal(delivery_cost_raw) if delivery_cost_raw else None
            except (TypeError, ValueError):
                delivery_cost_val = None

            with db_transaction.atomic():
                order = Order.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    name=name,
                    email=email,
                    phone=phone,
                    delivery_method=dm,
                    delivery_city=delivery_city,
                    delivery_address=delivery_address,
                    cdek_city_code=cdek_code,
                    cdek_pvz_code=cdek_pvz_code or "",
                    fivepost_pvz_id=fivepost_pvz_id or "",
                    russianpost_to_index=russianpost_to_index[:6] if russianpost_to_index else "",
                    delivery_cost=delivery_cost_val,
                    payment_type=payment_type,
                    total=total,
                    total_pv=total_pv,
                    status=Order.Status.NEW,
                    comment=comment,
                )

                for item in items:
                    v = item["variant"]
                    qty = item["qty"]
                    if v.stock < qty:
                        order.delete()
                        messages.error(request, f"Недостаточно товара «{v.product.name}» на складе.")
                        return redirect("catalog:checkout")
                    OrderItem.objects.create(
                        order=order,
                        variant=v,
                        quantity=qty,
                        price=v.price,
                        pv=getattr(v, "pv", 0) or 0,
                    )
                    v.stock -= qty
                    v.save(update_fields=["stock"])

                set_cart(request, {})
                return redirect("catalog:order_success", order_id=order.pk)
    except Exception as e:
        log.exception("checkout error: %s", e)
        messages.error(request, "Произошла ошибка при оформлении. Попробуйте ещё раз.")
        return redirect("catalog:checkout")


def _checkout_lock():
    """Контекстный менеджер для блокировки при оформлении (пока заглушка)."""
    from contextlib import nullcontext
    return nullcontext()


def order_success_view(request, order_id):
    """Страница «Заказ принят»."""
    from orders.models import Order
    order = get_object_or_404(Order, pk=order_id)
    return render(request, "catalog/order_success.html", {"order": order})


def policy_view(request):
    """Страница «Политика конфиденциальности»."""
    return render(request, "catalog/policy.html")


def _get_favorites(request):
    """Получить список ID товаров в избранном."""
    ids = request.session.get("favorites", [])
    if not isinstance(ids, list):
        return []
    return [int(x) for x in ids if isinstance(x, (int, str)) and str(x).isdigit()]


def _set_favorites(request, ids):
    """Сохранить избранное в сессию."""
    request.session["favorites"] = list(ids)
    request.session.modified = True


def _get_recent_viewed(request, exclude=None, limit=8):
    """Получить список ID недавно просмотренных товаров."""
    ids = request.session.get("recent_viewed", [])
    if not isinstance(ids, list):
        return []
    out = [int(x) for x in ids if isinstance(x, (int, str)) and str(x).isdigit()]
    seen = set()
    unique = []
    for x in out:
        if x not in seen and x != exclude:
            seen.add(x)
            unique.append(x)
        if len(unique) >= limit:
            break
    return unique


def _add_recent_viewed(request, product_id):
    """Добавить товар в недавно просмотренные."""
    ids = _get_recent_viewed(request, exclude=product_id, limit=20)
    ids.insert(0, product_id)
    request.session["recent_viewed"] = ids[:12]
    request.session.modified = True


def favorites_view(request):
    """Страница избранного."""
    ids = _get_favorites(request)
    products = Product.objects.filter(
        pk__in=ids, is_active=True
    ).exclude(slug__isnull=True).exclude(slug="").select_related("category", "brand").prefetch_related("variants", "media")
    products = list(products)
    order = {pid: i for i, pid in enumerate(ids)}
    products.sort(key=lambda p: order.get(p.pk, 999))
    cart = get_cart(request)
    for p in products:
        p.root_category_slug = p.category.get_root().slug if p.category else ""
        p.default_variant = p.variants.filter(is_default=True).first() or p.variants.first()
        p.main_image = p.media.filter(media_type="image").first()
        p.variants_list = list(p.variants.all())
        p.cart_qty = _product_cart_qty(cart, p.pk)
        p.is_in_favorites = True
    return render(request, "catalog/favorites.html", {"products": products})


@require_POST
def favorites_toggle(request, product_id):
    """Добавить/убрать товар из избранного."""
    try:
        product_id = int(product_id)
    except (TypeError, ValueError):
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "error": "Неверные данные"}, status=400)
        return redirect("catalog:product_list")
    if not Product.objects.filter(pk=product_id, is_active=True).exists():
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"ok": False, "error": "Товар не найден"}, status=404)
        return redirect("catalog:product_list")
    ids = _get_favorites(request)
    if product_id in ids:
        ids = [x for x in ids if x != product_id]
        added = False
    else:
        ids.append(product_id)
        added = True
    _set_favorites(request, ids)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "added": added, "count": len(ids)})
    next_url = request.GET.get("next") or request.META.get("HTTP_REFERER") or reverse("catalog:product_list")
    return redirect(next_url)

def cities_autocomplete(request):
    """Подсказки городов для поля «Город» на чекауте. GET ?q=мо → JSON список названий."""
    from orders.models import City

    q = (request.GET.get("q") or "").strip()[:80]
    if not q:
        return JsonResponse([], safe=False)
    cities = list(
        City.objects.filter(name__icontains=q).values_list("name", flat=True).order_by("name")[:20]
    )
    return JsonResponse(cities, safe=False)

