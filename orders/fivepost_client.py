"""
Клиент 5post API (доставка X5). JWT по api-key, расчёт тарифа по зонам (локально), список ПВЗ.
Документация: https://fivepost.ru (партнёрам), SDK: https://github.com/lapaygroup/fivepost-sdk
Базовые URL: api-omni.x5.ru (prod), api-preprod-omni.x5.ru (test).
"""
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

from django.conf import settings

logger = logging.getLogger(__name__)

# Тарифы по зонам (из SDK TariffsTrait — при индивидуальном договоре можно переопределить)
FIVEPOST_ZONE_TARIFFS = {
    1: {"basic_price": 187, "overload_kg_price": 18, "delivery_days": 3},
    2: {"basic_price": 220, "overload_kg_price": 18, "delivery_days": 3},
    3: {"basic_price": 248, "overload_kg_price": 19, "delivery_days": 3},
    4: {"basic_price": 286, "overload_kg_price": 36, "delivery_days": 6},
    5: {"basic_price": 334, "overload_kg_price": 48, "delivery_days": 6},
    6: {"basic_price": 321, "overload_kg_price": 38, "delivery_days": 6},
    7: {"basic_price": 403, "overload_kg_price": 54, "delivery_days": 6},
    8: {"basic_price": 423, "overload_kg_price": 66, "delivery_days": 9},
    9: {"basic_price": 518, "overload_kg_price": 113, "delivery_days": 10},
    10: {"basic_price": 481, "overload_kg_price": 70, "delivery_days": 8},
    11: {"basic_price": 551, "overload_kg_price": 70, "delivery_days": 8},
    12: {"basic_price": 551, "overload_kg_price": 117, "delivery_days": 8},
    13: {"basic_price": 578, "overload_kg_price": 194, "delivery_days": 9},
}
FIVEPOST_WEIGHT_BASIC_KG = 3  # до этого веса — базовый тариф

_fivepost_jwt: Optional[str] = None
_fivepost_jwt_expire: float = 0


def _base_url() -> str:
    url = getattr(settings, "FIVEPOST_API_URL", None)
    if url:
        return url.rstrip("/")
    if getattr(settings, "FIVEPOST_TEST", False):
        return "https://api-preprod-omni.x5.ru"
    return "https://api-omni.x5.ru"


def get_jwt(force: bool = False) -> Optional[str]:
    """Получить JWT 5post (кэш ~50 мин). POST /jwt-generate-claims/rs256/1?apikey=..."""
    global _fivepost_jwt, _fivepost_jwt_expire
    if not force and _fivepost_jwt and time.time() < _fivepost_jwt_expire:
        return _fivepost_jwt

    api_key = getattr(settings, "FIVEPOST_API_KEY", None) or ""
    if not api_key:
        logger.warning("5post: FIVEPOST_API_KEY не задан")
        return None

    base = _base_url()
    url = f"{base}/jwt-generate-claims/rs256/1?apikey={urllib.parse.quote(api_key)}"
    data = urllib.parse.urlencode({"subject": "OpenAPI", "audience": "A122019!"}).encode()
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode())
            _fivepost_jwt = body.get("jwt")
            # JWT живёт 1 час
            _fivepost_jwt_expire = time.time() + 3500
            return _fivepost_jwt
    except (TimeoutError, OSError) as e:
        logger.warning("5post JWT timeout: %s", e)
        _fivepost_jwt = None
        _fivepost_jwt_expire = 0
        return None
    except urllib.error.HTTPError as e:
        err_body = e.read().decode(errors="replace")[:500]
        logger.warning("5post JWT error %s: %s", e.code, err_body)
        _fivepost_jwt = None
        _fivepost_jwt_expire = 0
        return None
    except (urllib.error.URLError, json.JSONDecodeError, KeyError) as e:
        logger.warning("5post JWT error: %s", e)
        _fivepost_jwt = None
        _fivepost_jwt_expire = 0
        return None


def get_zone_for_city(city_name: str) -> int:
    """Тарифная зона по названию города. Маппинг из настроек FIVEPOST_CITY_ZONE или встроенный по умолчанию."""
    mapping = getattr(settings, "FIVEPOST_CITY_ZONE", None) or {}
    key = (city_name or "").strip().lower()
    if not key:
        return 1
    for name, zone in mapping.items():
        if name == "__default__":
            continue
        if name.lower() in key or key in name.lower():
            try:
                return int(zone)
            except (TypeError, ValueError):
                pass
    default = mapping.get("__default__", 1)
    try:
        return int(default)
    except (TypeError, ValueError):
        return 1


def calculation_tariff(
    zone: int,
    weight_grams: int,
    amount: float = 0,
    payment_prepaid: bool = True,
    return_on_noredeem: bool = False,
) -> dict:
    """
    Расчёт стоимости и срока доставки 5post по зоне (локально, как в SDK).
    weight_grams — вес в граммах, amount — оценочная стоимость (для наложенного платежа).
    Возвращает {"price": float, "delivery_days": int}.
    """
    zone = int(zone)
    if zone not in FIVEPOST_ZONE_TARIFFS:
        zone = 1
    t = FIVEPOST_ZONE_TARIFFS[zone]
    weight_kg = weight_grams / 1000.0
    if weight_kg > FIVEPOST_WEIGHT_BASIC_KG:
        import math
        overload_kg = math.ceil(weight_kg - FIVEPOST_WEIGHT_BASIC_KG)
        price = t["basic_price"] + overload_kg * t["overload_kg_price"]
    else:
        price = t["basic_price"]

    if return_on_noredeem:
        price += price * 0.50
    if amount > 0:
        price += amount * 0.005
        if not payment_prepaid:
            price += amount * 0.0192  # cash

    return {
        "price": round(price, 2),
        "delivery_days": t["delivery_days"],
    }


def get_delivery_cost(
    city_name: str,
    weight_grams: int,
    amount: float = 0,
    payment_prepaid: bool = True,
) -> Optional[dict]:
    """
    Расчёт доставки 5post: город → зона → тариф.
    Возвращает {"price": float, "delivery_days": int, "zone": int} или None.
    """
    zone = get_zone_for_city(city_name)
    result = calculation_tariff(zone, weight_grams, amount, payment_prepaid, return_on_noredeem=False)
    result["zone"] = zone
    return result


def _request_post(path: str, body: dict, timeout: int = 20, _retry: bool = True) -> Optional[dict]:
    """POST с JWT. При 401 — обновление токена и повтор."""
    token = get_jwt()
    if not token:
        return None
    base = _base_url()
    url = f"{base}{path}"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode(errors="replace")[:500]
        logger.warning("5post API POST %s error %s: %s", path, e.code, err_body)
        if e.code in (401, 403) and _retry:
            global _fivepost_jwt, _fivepost_jwt_expire
            _fivepost_jwt = None
            _fivepost_jwt_expire = 0
            return _request_post(path, body, timeout, _retry=False)
        return None
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError) as e:
        logger.warning("5post API POST %s error: %s", path, e)
        return None


def get_pvz_list(page: int = 0, size: int = 500) -> Optional[dict]:
    """Список ПВЗ (постранично). POST /api/v1/pickuppoints/query."""
    return _request_post("/api/v1/pickuppoints/query", {"pageNumber": page, "pageSize": size}, timeout=30)


def get_pvz_by_city(city_name: str, max_results: int = 50) -> list:
    """
    ПВЗ в заданном городе. Загружает страницы и фильтрует по address.city.
    Город сравнивается без учёта регистра и лишних пробелов.
    """
    city_clean = (city_name or "").strip().lower()
    if not city_clean:
        return []
    results = []
    page = 0
    page_size = 500
    while len(results) < max_results:
        resp = get_pvz_list(page, page_size)
        if not resp:
            break
        content = resp.get("content") if isinstance(resp.get("content"), list) else []
        if not content:
            break
        for p in content:
            addr = p.get("address") or {}
            c = (addr.get("city") or "").strip().lower()
            if city_clean in c or c in city_clean:
                results.append({
                    "id": p.get("id"),
                    "code": p.get("mdmCode") or p.get("id"),
                    "name": p.get("name") or p.get("mdmCode", ""),
                    "address": p.get("fullAddress") or p.get("shortAddress", ""),
                    "city": addr.get("city", ""),
                })
                if len(results) >= max_results:
                    return results
        total_pages = resp.get("totalPages") or 0
        page += 1
        if page >= total_pages:
            break
    return results
