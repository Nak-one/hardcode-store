"""
Клиент СДЭК API v2.0 для расчёта доставки и списка ПВЗ.
Учётные данные: CDEK_ACCOUNT, CDEK_SECURE (запросить у integrator@cdek.ru).
Документация: https://api-docs.cdek.ru/
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

# Базовые URL СДЭК API v2
CDEK_API_URL = "https://api.cdek.ru"
CDEK_API_URL_TEST = "https://api.edu.cdek.ru"  # тестовый стенд (integration.edu.cdek.ru может отдавать 403)
CDEK_OAUTH_PATH = "/v2/oauth/token"

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
    POST /v2/oauth/token, grant_type=client_credentials, client_id=account, client_secret=secure.
    """
    global _cdek_token, _cdek_token_expire
    if not force and _cdek_token and time.time() < _cdek_token_expire:
        return _cdek_token

    account, secure = _get_credentials()
    if not account or not secure:
        logger.warning("CDEK: учётные данные не заданы (CDEK_ACCOUNT, CDEK_SECURE)")
        return None

    base = _base_url()
    url = f"{base}{CDEK_OAUTH_PATH}"
    data = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": account,
        "client_secret": secure,
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "User-Agent": "HardcodeStore/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode())
            _cdek_token = body.get("access_token")
            expires_in = int(body.get("expires_in", 3599)) - 10
            _cdek_token_expire = time.time() + expires_in
            return _cdek_token
    except (TimeoutError, OSError) as e:
        logger.warning("CDEK OAuth timeout: %s", e)
        _cdek_token = None
        _cdek_token_expire = 0
        return None
    except urllib.error.HTTPError as e:
        err_body = e.read().decode(errors="replace")[:500]
        logger.warning("CDEK OAuth error %s: %s", e.code, err_body)
        _cdek_token = None
        _cdek_token_expire = 0
        return None
    except (urllib.error.URLError, json.JSONDecodeError, KeyError) as e:
        logger.warning("CDEK OAuth error: %s", e)
        _cdek_token = None
        _cdek_token_expire = 0
        return None


def _request(method: str, path: str, body: Optional[dict] = None, timeout: int = 20, _retry: bool = True) -> Optional[dict]:
    """Выполнить запрос к API с текущим токеном. При 401 — сброс токена и одна повторная попытка."""
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
    req.add_header("User-Agent", "HardcodeStore/1.0")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except (TimeoutError, OSError) as e:
        if "timed out" in str(e).lower() or "timeout" in str(type(e).__name__).lower():
            logger.warning("CDEK API %s %s timeout", method, path)
        else:
            logger.warning("CDEK API %s %s error: %s", method, path, e)
        return None
    except urllib.error.HTTPError as e:
        err_body = e.read().decode(errors="replace")[:500]
        logger.warning("CDEK API %s %s error %s: %s", method, path, e.code, err_body)
        if e.code in (401, 403) and _retry:
            global _cdek_token, _cdek_token_expire
            _cdek_token = None
            _cdek_token_expire = 0
            logger.info("CDEK: токен недействителен (%s), запрашиваем новый", e.code)
            return _request(method, path, body, timeout, _retry=False)
        return None
    except (urllib.error.URLError, json.JSONDecodeError) as e:
        logger.warning("CDEK API %s %s error: %s", method, path, e)
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
    Коды городов — из справочника СДЭК (get_cities).
    Вес в граммах, габариты в см.
    Если tariff_code задан — расчёт по одному тарифу (/v2/calculator/tariff).
    Иначе — список доступных тарифов (/v2/calculator/tarifflist).
    """
    packages = [{
        "weight": weight_grams,
        "length": length_cm,
        "width": width_cm,
        "height": height_cm,
    }]
    if tariff_code is not None:
        payload = {
            "tariff_code": tariff_code,
            "from_location": {"code": from_city_code},
            "to_location": {"code": to_city_code},
            "packages": packages,
        }
        return _request("POST", "/v2/calculator/tariff", payload)
    payload = {
        "from_location": {"code": from_city_code},
        "to_location": {"code": to_city_code},
        "packages": packages,
    }
    return _request("POST", "/v2/calculator/tarifflist", payload)


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
    if isinstance(resp, list):
        return resp
    return resp.get("items") or resp.get("delivery_points") or []


_cities_cache: list = []
_cities_cache_time: float = 0
_CITIES_CACHE_TTL = 3600  # 1 час


def _get_cities_full(country_code: str = "RU", timeout: int = 12) -> list:
    """Получить полный список городов (с кэшем) для поиска по подстроке."""
    global _cities_cache, _cities_cache_time
    import time
    now = time.time()
    if _cities_cache and (now - _cities_cache_time) < _CITIES_CACHE_TTL:
        return _cities_cache
    path = f"/v2/location/cities?country_codes={urllib.parse.quote(country_code)}&size=3000"
    resp = _request("GET", path, timeout=timeout)
    if resp is None:
        return _cities_cache if _cities_cache else []
    items = resp if isinstance(resp, list) else (
        resp.get("items") or resp.get("cities") or resp.get("data") or []
    )
    if items:
        _cities_cache = items
        _cities_cache_time = now
    return _cities_cache


def get_cities(country_code: str = "RU", name_filter: Optional[str] = None) -> Optional[list]:
    """
    Список городов СДЭК. API требует точное совпадение — для подстроки (Новоси→Новосибирск)
    используем fallback: полный список с поиском по подстроке (timeout 12 сек).
    """
    if name_filter:
        path = "/v2/location/cities"
        params = [
            f"country_codes={urllib.parse.quote(country_code)}",  # v2 API использует country_codes
            f"city={urllib.parse.quote(name_filter)}",
            "size=100",
        ]
        path += "?" + "&".join(params)
        resp = _request("GET", path, timeout=10)
        if resp is not None:
            items = resp if isinstance(resp, list) else (
        resp.get("items") or resp.get("cities") or resp.get("data") or []
    )
            if items:
                return items
        # Fallback: поиск по подстроке в полном списке (API требует точное совпадение)
        all_cities = _get_cities_full(country_code, timeout=12)
        q_lower = name_filter.lower().strip()
        matched = [c for c in all_cities if q_lower in (c.get("city") or "").lower()]
        return matched[:30] if matched else None
    return None
