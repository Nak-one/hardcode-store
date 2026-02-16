"""Хранение корзины — только сессия Django (session в БД)."""
from .cart_logic import get_raw_cart
from .cart_log import log, _cart_repr


def _is_new_format(data):
    """Проверка: корзина в новом формате {i_xxx: {p, v, q}}."""
    if not data or not isinstance(data, dict):
        return False
    for k, v in data.items():
        if not isinstance(v, dict):
            return False
        if "p" not in v:
            return False
    return True


def get_cart(request):
    """Получить корзину в новом формате."""
    raw = dict(request.session.get("cart", {}))
    sk = getattr(request.session, "session_key", None) or "(no key)"
    log.info("[get_cart] session_key=%s raw_keys=%s is_new_format=%s", sk, list(raw.keys()), _is_new_format(raw))
    if not _is_new_format(raw):
        raw = {}
    out = get_raw_cart(raw)
    log.info("[get_cart] result_keys=%s cart=%s", list(out.keys()), _cart_repr(out))
    return out


def set_cart(request, cart):
    """Сохранить корзину в сессию."""
    cart_dict = get_raw_cart(cart) if cart else {}
    sk = getattr(request.session, "session_key", None) or "(no key)"
    log.info("[set_cart] session_key=%s saving_keys=%s cart=%s", sk, list(cart_dict.keys()), _cart_repr(cart_dict))
    request.session["cart"] = cart_dict
    request.session.modified = True
    request.session.save()
    log.info("[set_cart] done")
