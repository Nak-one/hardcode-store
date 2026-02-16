"""Логгер для отладки корзины и товаров с вариантами."""
import logging
import json

log = logging.getLogger("catalog.cart")


def _cart_repr(cart):
    """Короткое представление корзины для логов."""
    if not cart:
        return "{}"
    return json.dumps(cart, ensure_ascii=False, default=str)
