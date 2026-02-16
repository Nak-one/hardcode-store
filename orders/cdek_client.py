"""
Клиент СДЭК API v2.0 для расчёта доставки и списка ПВЗ.
Учётные данные: CDEK_ACCOUNT, CDEK_SECURE (запросить у integrator@cdek.ru).
Документация: https://apidoc.cdek.ru/
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

from django.conf import settings

# Базовые URL из документации СДЭК
CDEK_API_URL = "https://api.cdek.ru"
CDEK_API_URL_TEST = "https://integration.edu.cdek.ru"

_cdek_token: Optional[str] = None
_cdek_token_expire: float = 0


def _base_url() -> str:
    url = getattr(settings, "CDEK_BASE_URL", None)
    if url:
        return url.rstrip("/")
    if getattr(settings, "CDEK_TEST", False):
        return CDEK_API_URL_TEST
    return CDEK_API_URL


def _get_credentials() -> tuple[str, str]:
    account = getattr(settings, "CDEK_ACCOUNT", None) or ""
    secure = getattr(settings, "CDEK_SECURE", None) or ""
    return account, secure


def get_token(force: bool = False) -> Optional[str]:
    """
    Получить OAuth-токен СДЭК (кэш ~6 мин).
    POST /oauth/token, grant_type=client_credentials, client_id=account, client_secret=secure.
    """
    global _cdek_token, _cdek_token_expire
    if not force and _cdek_token and time.time() < _cdek_token_expire:
        return _cdek_token

    account, secure = _get_credentials()
    if not account or not secure:
        return None

    base = _base_url()
    url = f"{base}/oauth/token"
    data = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": account,
        "client_secret": secure,
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode())
            _cdek_token = body.get("access_token")
            expires_in = int(body.get("expires_in", 3599)) - 10
            _cdek_token_expire = time.time() + expires_in
            return _cdek_token
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError, KeyError):
        _cdek_token = None
        _cdek_token_expire = 0
        return None


def _request(method: str, path: str, body: Optional[dict] = None) -> Optional[dict]:
    """Выполнить запрос к API с текущим токеном."""
    token = get_token()
    if not token:
        return None
    base = _base_url()
    url = f"{base}{path}"
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    data = None
    if body and method != "GET":
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError):
        return None


def get_delivery_cost(
    from_city_code: int,
    to_city_code: int,
    weight_grams: int,
    length_cm: int = 10,
    width_cm: int = 10,
    height_cm: int = 10,
    tariff_code: Optional[int] = None,
) -> Optional[dict]:
    """
    Расчёт стоимости и срока доставки (калькулятор тарифов).
    Коды городов — из справочника СДЭК (cities).
    Вес в граммах, габариты в см.
    Возвращает ответ API или None при ошибке.
    Точный путь и формат тела см. в актуальной документации: https://apidoc.cdek.ru/
    """
    # Пример тела по документации калькулятора (уточнить путь в apidoc.cdek.ru)
    payload = {
        "from_location": {"code": from_city_code},
        "to_location": {"code": to_city_code},
        "packages": [{
            "weight": weight_grams,
            "length": length_cm,
            "width": width_cm,
            "height": height_cm,
        }],
    }
    if tariff_code is not None:
        payload["tariff_code"] = tariff_code
    # Путь может быть /v2/calculator/tariff или /v2/calculator/tarifflist — см. документацию
    return _request("POST", "/v2/calculator/tariff", payload)


def get_delivery_points(country_code: str = "RU", city_code: Optional[int] = None) -> Optional[list]:
    """
    Список ПВЗ (пунктов выдачи). Фильтр по стране и опционально по коду города.
    Возвращает list пунктов или None.
    """
    path = "/v2/deliverypoints"
    params = []
    if country_code:
        params.append(f"country_code={urllib.parse.quote(country_code)}")
    if city_code is not None:
        params.append(f"city_code={city_code}")
    if params:
        path += "?" + "&".join(params)
    resp = _request("GET", path)
    if resp is None:
        return None
    # Формат ответа уточнить по документации (items / delivery_points и т.д.)
    return resp.get("items") or resp.get("delivery_points") or []


def get_cities(country_code: str = "RU", name_filter: Optional[str] = None) -> Optional[list]:
    """
    Список городов СДЭК (для подсказок и получения code). Фильтр по стране и названию.
    """
    path = "/v2/location/cities"
    params = [f"country_code={urllib.parse.quote(country_code)}"]
    if name_filter:
        params.append(f"city={urllib.parse.quote(name_filter)}")
    path += "?" + "&".join(params)
    resp = _request("GET", path)
    if resp is None:
        return None
    return resp.get("items") or resp.get("cities") or []
