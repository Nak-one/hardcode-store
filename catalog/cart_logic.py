"""
Логика корзины — единая структура для всех типов товаров.

Формат корзины: { "i_xxxxxxxx": {"p": product_id, "v": variant_id, "q": qty} }
- p: product_id (int)
- v: variant_id (int) или None — None = нужно выбрать характеристику (плейсхолдер)
- q: количество (int), для товаров с вариантами всегда 1

Правила:
- Товар с вариантами из каталога: v=None, q=1
- Товар с вариантами из карточки: v=variant_id, q=1
- Простой товар: v=variant_id, q может быть > 1
"""
import uuid


def _new_id():
    return f"i_{uuid.uuid4().hex[:12]}"


def _normalize(cart):
    """Привести к единому формату. Старые данные игнорируются."""
    out = {}
    for k, val in (cart or {}).items():
        if not isinstance(val, dict):
            continue
        p = val.get("p")
        v = val.get("v")
        q = val.get("q", 1)
        if p is None:
            continue
        try:
            p = int(p)
        except (TypeError, ValueError):
            continue
        if q is None:
            q = 1
        try:
            q = max(1, int(q))
        except (TypeError, ValueError):
            q = 1
        if v is not None and v != "":
            try:
                v = int(v)
            except (TypeError, ValueError):
                v = None
        else:
            v = None
        if not str(k).startswith("i_"):
            k = _new_id()
        out[str(k)] = {"p": p, "v": v, "q": q}
    return out


def get_raw_cart(cart):
    """Вернуть нормализованную корзину (для хранения)."""
    return _normalize(cart)


def cart_total_count(cart):
    """Общее количество единиц в корзине."""
    cart = _normalize(cart)
    return sum(item["q"] for item in cart.values())


def cart_items_for_product(cart, product_id):
    """Все ключи корзины, относящиеся к product_id."""
    cart = _normalize(cart)
    return [k for k, item in cart.items() if item["p"] == product_id]


def add_from_catalog(cart, product_id, variant_id, qty=1, has_variants=False):
    """
    Добавить из каталога.
    - has_variants=True: новая строка с v=None (плейсхолдер)
    - has_variants=False: найти существующую по variant_id, иначе добавить
    """
    from .cart_log import log
    cart = _normalize(cart)
    if has_variants:
        new_key = _new_id()
        cart[new_key] = {"p": product_id, "v": None, "q": 1}
        log.info("[add_from_catalog] has_variants=True added placeholder key=%s product_id=%s", new_key, product_id)
        return cart
    for k, item in cart.items():
        if item["p"] == product_id and item["v"] == variant_id:
            item["q"] = item["q"] + qty
            return cart
    cart[_new_id()] = {"p": product_id, "v": variant_id, "q": qty}
    return cart


def add_from_detail(cart, product_id, variant_id, qty=1, has_variants=False):
    """
    Добавить из карточки товара (вариант уже выбран).
    Товары с вариантами — каждая единица отдельной строкой (как из каталога).
    Простые товары — объединяем в одну строку.
    """
    from .cart_log import log
    cart = _normalize(cart)
    if has_variants:
        for _ in range(qty):
            cart[_new_id()] = {"p": product_id, "v": variant_id, "q": 1}
        log.info("[add_from_detail] has_variants added %s rows product_id=%s variant_id=%s", qty, product_id, variant_id)
        return cart
    for k, item in cart.items():
        if item["p"] == product_id and item["v"] == variant_id:
            item["q"] = item["q"] + qty
            log.info("[add_from_detail] merged key=%s product_id=%s variant_id=%s qty=%s", k, product_id, variant_id, item["q"])
            return cart
    cart[_new_id()] = {"p": product_id, "v": variant_id, "q": qty}
    log.info("[add_from_detail] new key product_id=%s variant_id=%s qty=%s", product_id, variant_id, qty)
    return cart


def replace_variant(cart, item_id, new_variant_id):
    """
    Заменить вариант в строке (для плейсхолдера).
    item_id — ключ в корзине.
    Возвращает обновлённую корзину или None если не найдено.
    """
    from .cart_log import log
    cart = _normalize(cart)
    keys = list(cart.keys())
    log.info("[replace_variant] item_id=%r new_variant_id=%s cart_keys=%s", item_id, new_variant_id, keys)
    if item_id not in cart:
        log.warning("[replace_variant] item_id NOT IN cart (key not found)")
        return None
    item = cart[item_id]
    if item["v"] is not None:
        log.warning("[replace_variant] item already has v=%s (not placeholder)", item["v"])
        return None  # уже выбран, не заменяем
    try:
        item["v"] = int(new_variant_id)
    except (TypeError, ValueError) as e:
        log.warning("[replace_variant] invalid new_variant_id: %s", e)
        return None
    log.info("[replace_variant] OK updated item %s v=%s", item_id, item["v"])
    return cart


def remove_item(cart, item_id):
    """Удалить строку по id."""
    cart = _normalize(cart)
    cart.pop(item_id, None)
    return cart


def remove_last_for_product(cart, product_id):
    """Удалить последнюю строку товара (последнюю в порядке итерации)."""
    cart = _normalize(cart)
    last_key = None
    for k, item in cart.items():
        if item["p"] == product_id:
            last_key = k
    if last_key:
        cart.pop(last_key, None)
    return cart


def remove_last_for_variant(cart, product_id, variant_id):
    """Удалить последнюю строку товара с указанным вариантом."""
    cart = _normalize(cart)
    try:
        variant_id = int(variant_id)
    except (TypeError, ValueError):
        return cart
    last_key = None
    for k, item in cart.items():
        if item["p"] == product_id and item.get("v") == variant_id:
            last_key = k
    if last_key:
        cart.pop(last_key, None)
    return cart


def set_qty(cart, item_id, qty):
    """Установить количество для строки по cart_key (i_xxx)."""
    cart = _normalize(cart)
    if item_id not in cart:
        return None
    item = cart[item_id]
    qty = max(0, int(qty)) if qty is not None else 0
    if qty == 0:
        cart.pop(item_id, None)
    else:
        item["q"] = qty
    return cart


def set_qty_by_variant(cart, product_id, variant_id, qty):
    """
    Найти строку по product_id + variant_id (для простых товаров) и установить qty.
    Если не найдено и qty > 0 — добавить новую строку.
    """
    cart = _normalize(cart)
    variant_id = int(variant_id)
    product_id = int(product_id)
    qty = max(0, int(qty)) if qty is not None else 0
    for k, item in cart.items():
        if item["p"] == product_id and item["v"] == variant_id:
            if qty == 0:
                cart.pop(k, None)
            else:
                item["q"] = qty
            return cart
    if qty > 0:
        cart[_new_id()] = {"p": product_id, "v": variant_id, "q": qty}
    return cart
