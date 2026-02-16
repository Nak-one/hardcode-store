def hide_hero_nav(request):
    """Скрывать hero и фильтры категорий на корзине, карточке товара, ЛК, оформлении заказа, избранном, авторизации."""
    url_name = getattr(request.resolver_match, "url_name", "") if request.resolver_match else ""
    return {"hide_hero_nav": url_name in (
        "cart", "cart_replace", "checkout", "order_success", "product_detail", "favorites", "policy",
        "register", "login",
        "cabinet", "profile", "password_change", "referral", "business_join",
        "order_detail", "orders_list", "address_list", "address_add", "address_edit", "address_delete", "address_set_default",
    )}


def favorites_count(request):
    """Количество товаров в избранном для бейджа в шапке."""
    ids = request.session.get("favorites", [])
    if not isinstance(ids, list):
        return {"favorites_count": 0}
    n = len([x for x in ids if isinstance(x, (int, str)) and str(x).isdigit()])
    return {"favorites_count": n}


def cart_count(request):
    from .cart_storage import get_cart
    from .cart_logic import cart_total_count
    cart = get_cart(request)
    return {"cart_count": cart_total_count(cart)}


def nav_categories(request):
    from .models import Category, Product
    from django.db.models import Count, Subquery, OuterRef

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
    return {"categories": list(categories)}
