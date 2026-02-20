import re
from datetime import datetime, timezone as dt_timezone

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from .cdek_client import get_cities, get_delivery_cost, get_delivery_points, get_token
from .fivepost_client import get_delivery_cost as fivepost_get_delivery_cost, get_pvz_by_city
from .models import City, Order, OrderSyncQueue
from .russianpost_client import get_delivery_cost as russianpost_get_delivery_cost
from .sync_queue import _order_to_payload


def _cdek_diagnose_step(name, timeout_sec, callable_fn):
    """Выполнить шаг диагностики, вернуть {ok, time_ms, error}."""
    import time
    t0 = time.time()
    try:
        result = callable_fn()
        elapsed = (time.time() - t0) * 1000
        return {"step": name, "ok": result is not None and result is not False, "time_ms": round(elapsed), "error": None}
    except Exception as e:
        elapsed = (time.time() - t0) * 1000
        err = f"{type(e).__name__}: {str(e)[:150]}"
        return {"step": name, "ok": False, "time_ms": round(elapsed), "error": err}


@require_GET
def cdek_diagnostic_api(request):
    """
    Подробная диагностика CDEK API. GET /api/cdek/diagnostic/
    Проверяет по шагам: OAuth, города, расчёт доставки, ПВЗ. Время и ошибка на каждом шаге.
    """
    import time
    import urllib.request
    import urllib.parse
    import json
    from django.conf import settings

    base = getattr(settings, "CDEK_BASE_URL", None) or (
        "https://api.edu.cdek.ru" if getattr(settings, "CDEK_TEST", False) else "https://api.cdek.ru"
    )
    account = getattr(settings, "CDEK_ACCOUNT", None) or ""
    secure = getattr(settings, "CDEK_SECURE", None) or ""

    steps = []
    token = None

    # 1. OAuth
    def _oauth():
        nonlocal token
        url = f"{base}/v2/oauth/token"
        data = urllib.parse.urlencode({
            "grant_type": "client_credentials", "client_id": account, "client_secret": secure,
        }).encode()
        req = urllib.request.Request(url, data=data, method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            body = json.loads(resp.read().decode())
            token = body.get("access_token")
            return token
    steps.append(_cdek_diagnose_step("1_oauth_token", 8, _oauth))

    if token:
        # 2. Cities (filtered)
        def _cities():
            url = f"{base}/v2/location/cities?country_codes=RU&city=Москва&size=10"
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode())
                items = data.get("items") or data.get("cities") or (data if isinstance(data, list) else [])
                return len(items)
        steps.append(_cdek_diagnose_step("2_cities_filtered", 8, _cities))

        # 3. Delivery cost (Moscow 44 -> Novosibirsk 270)
        def _delivery():
            url = f"{base}/v2/calculator/tarifflist"
            payload = {
                "from_location": {"code": 44},
                "to_location": {"code": 270},
                "packages": [{"weight": 1000, "length": 20, "width": 15, "height": 10}],
            }
            data = json.dumps(payload).encode()
            req = urllib.request.Request(url, data=data, method="POST",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                r = json.loads(resp.read().decode())
                return len(r.get("tariff_codes") or [])
        steps.append(_cdek_diagnose_step("3_delivery_cost", 10, _delivery))

        # 4. PVZ (Novosibirsk 270)
        def _pvz():
            url = f"{base}/v2/deliverypoints?country_code=RU&city_code=270"
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                items = data.get("items") or data.get("delivery_points") or (data if isinstance(data, list) else [])
                return len(items)
        steps.append(_cdek_diagnose_step("4_pvz_list", 10, _pvz))

    return JsonResponse({
        "base_url": base,
        "has_credentials": bool(account and secure),
        "steps": steps,
        "summary": "Все шаги ок" if all(s["ok"] for s in steps) else "Есть ошибки — см. steps",
    }, json_dumps_params={"ensure_ascii": False})


@require_GET
def cdek_refresh_token_api(request):
    """Принудительно обновить токен СДЭК. GET /api/cdek/refresh-token/ — при ошибке возвращает детали."""
    import json
    import time
    import urllib.error
    import urllib.parse
    import urllib.request
    from django.conf import settings

    base = getattr(settings, "CDEK_BASE_URL", None) or (
        "https://api.edu.cdek.ru" if getattr(settings, "CDEK_TEST", False) else "https://api.cdek.ru"
    )
    account = getattr(settings, "CDEK_ACCOUNT", None) or ""
    secure = getattr(settings, "CDEK_SECURE", None) or ""

    if not account or not secure:
        return JsonResponse({
            "ok": False,
            "message": "CDEK_ACCOUNT или CDEK_SECURE не заданы в .env",
            "detail": {"has_account": bool(account), "has_secure": bool(secure)},
        }, json_dumps_params={"ensure_ascii": False})

    url = f"{base}/v2/oauth/token"
    data = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": account,
        "client_secret": secure,
    }).encode()
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
    )

    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            body = json.loads(resp.read().decode())
            token = body.get("access_token")
            elapsed = round((time.time() - t0) * 1000)
            if token:
                import orders.cdek_client as cdek_mod
                cdek_mod._cdek_token = token
                cdek_mod._cdek_token_expire = time.time() + int(body.get("expires_in", 3599)) - 10
                return JsonResponse({
                    "ok": True,
                    "message": "Токен обновлён",
                    "detail": {"time_ms": elapsed, "base_url": base},
                }, json_dumps_params={"ensure_ascii": False})
            return JsonResponse({
                "ok": False,
                "message": "Ответ без access_token",
                "detail": {"time_ms": elapsed, "base_url": base, "keys": list(body.keys())[:10]},
            }, json_dumps_params={"ensure_ascii": False})
    except urllib.error.HTTPError as e:
        err_body = e.read().decode(errors="replace")[:300]
        elapsed = round((time.time() - t0) * 1000)
        try:
            err_json = json.loads(err_body)
        except Exception:
            err_json = {"raw": err_body}
        return JsonResponse({
            "ok": False,
            "message": f"СДЭК вернул {e.code}",
            "detail": {
                "status": e.code,
                "time_ms": elapsed,
                "base_url": base,
                "error": err_json.get("error", err_json.get("error_description", str(err_json))),
            },
        }, json_dumps_params={"ensure_ascii": False})
    except (TimeoutError, OSError) as e:
        elapsed = round((time.time() - t0) * 1000)
        return JsonResponse({
            "ok": False,
            "message": "Таймаут или нет соединения",
            "detail": {
                "error": type(e).__name__ + ": " + str(e)[:200],
                "time_ms": elapsed,
                "base_url": base,
            },
        }, json_dumps_params={"ensure_ascii": False})
    except Exception as e:
        elapsed = round((time.time() - t0) * 1000)
        return JsonResponse({
            "ok": False,
            "message": str(type(e).__name__),
            "detail": {"error": str(e)[:200], "time_ms": elapsed, "base_url": base},
        }, json_dumps_params={"ensure_ascii": False})


@require_GET
def cdek_status_api(request):
    """
    Диагностика API СДЭК. GET /api/cdek/status/
    Проверяет: учётные данные, токен, поиск городов (Москва).
    """
    from django.conf import settings
    has_creds = bool(
        getattr(settings, "CDEK_ACCOUNT", None) and getattr(settings, "CDEK_SECURE", None)
    )
    token_ok = False
    cities_ok = False
    cities_count = 0
    error = None
    if has_creds:
        try:
            token = get_token()
            token_ok = bool(token)
            if token_ok:
                cities = get_cities(country_code="RU", name_filter="Москва")
                if cities:
                    cities_ok = True
                    cities_count = len(cities)
                else:
                    error = "Города не найдены (проверьте доступ к api.cdek.ru)"
            else:
                error = "Не удалось получить токен СДЭК"
        except Exception as e:
            err_name = type(e).__name__
            if "timeout" in err_name.lower() or "timeout" in str(e).lower():
                error = f"Таймаут: api.cdek.ru не отвечает вовремя (сети/хостинг?)"
            else:
                error = f"{err_name}: {str(e)[:200]}"
    else:
        error = "CDEK_ACCOUNT и CDEK_SECURE не заданы в .env"
    return JsonResponse({
        "has_credentials": has_creds,
        "token_ok": token_ok,
        "cities_ok": cities_ok,
        "cities_test_count": cities_count,
        "error": error,
    }, json_dumps_params={"ensure_ascii": False})


# Fallback: основные города при таймауте СДЭК (code — код СДЭК)
_CDEK_CITIES_FALLBACK = [
    {"code": 44, "city": "Москва", "region": "Москва"},
    {"code": 137, "city": "Санкт-Петербург", "region": "Ленинградская"},
    {"code": 270, "city": "Новосибирск", "region": "Новосибирская"},
    {"code": 143, "city": "Екатеринбург", "region": "Свердловская"},
    {"code": 250, "city": "Краснодар", "region": "Краснодарский край"},
    {"code": 435, "city": "Казань", "region": "Татарстан"},
    {"code": 151, "city": "Нижний Новгород", "region": "Нижегородская"},
    {"code": 506, "city": "Самара", "region": "Самарская"},
    {"code": 442, "city": "Ростов-на-Дону", "region": "Ростовская"},
    {"code": 452, "city": "Уфа", "region": "Башкортостан"},
    {"code": 456, "city": "Челябинск", "region": "Челябинская"},
    {"code": 433, "city": "Воронеж", "region": "Воронежская"},
    {"code": 478, "city": "Пермь", "region": "Пермский край"},
    {"code": 38, "city": "Волгоград", "region": "Волгоградская"},
]


def _city_to_result(c):
    """Нормализация города из API: code может быть code или city_code."""
    code = c.get("code") or c.get("city_code")
    city = c.get("city") or c.get("city_name", "")
    region = c.get("region", "")
    try:
        code = int(code)
    except (TypeError, ValueError):
        code = 0
    return {"code": code, "city": city, "region": region}


@require_GET
def cdek_cities_api(request):
    """
    Подсказки городов из справочника СДЭК. Для шага доставки ТК СДЭК.
    GET /api/cdek/cities/?q=моск → {"results": [{"code": 44, "city": "Москва", "region": "Москва"}, ...]}
    ?debug=1 — диагностика. CDEK_CITIES_FALLBACK_ONLY=True — только локальный список (без API).
    """
    q = (request.GET.get("q") or "").strip()
    debug = request.GET.get("debug")
    if not q or len(q) < 2:
        return JsonResponse({"results": []}, json_dumps_params={"ensure_ascii": False})

    def _fallback_cities():
        q_lower = q.lower()
        return [c for c in _CDEK_CITIES_FALLBACK if q_lower in c["city"].lower()]

    fallback_only = getattr(settings, "CDEK_CITIES_FALLBACK_ONLY", False)
    if fallback_only:
        cities = _fallback_cities()
    else:
        try:
            cities = get_cities(country_code="RU", name_filter=q)
        except (TimeoutError, OSError, ConnectionError):
            cities = _fallback_cities()
        if not cities:
            cities = _fallback_cities()

    if debug:
        diag = {"query": q, "found": len(cities) if cities else 0}
        if cities and fallback_only:
            diag["source"] = "fallback_only"
        elif cities and not fallback_only:
            diag["source"] = "cdek_api_or_fallback"
        payload = {"results": [_city_to_result(c) for c in (cities or [])[:5]], "_debug": diag}
        resp = JsonResponse(payload, json_dumps_params={"ensure_ascii": False})
    else:
        results = [_city_to_result(c) for c in (cities or [])[:20]]
        resp = JsonResponse({"results": results}, json_dumps_params={"ensure_ascii": False})

    resp["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp["Pragma"] = "no-cache"
    return resp


@require_GET
def cdek_pvz_api(request):
    """
    Список ПВЗ СДЭК по коду города.
    GET /api/cdek/pvz/?city_code=44 → {"results": [{"code": "NSK1", "name": "...", "address": "..."}, ...]}
    """
    try:
        city_code = int(request.GET.get("city_code", 0))
    except (TypeError, ValueError):
        return JsonResponse({"results": []}, json_dumps_params={"ensure_ascii": False})
    if city_code <= 0:
        return JsonResponse({"results": []}, json_dumps_params={"ensure_ascii": False})
    points = get_delivery_points(country_code="RU", city_code=city_code)
    if not points:
        return JsonResponse({"results": []}, json_dumps_params={"ensure_ascii": False})
    results = []
    for p in points:
        loc = p.get("location") or {}
        results.append({
            "code": str(p.get("code", p.get("uuid", ""))),
            "name": p.get("name", ""),
            "address": loc.get("address", loc.get("address_full", "")),
            "work_time": p.get("work_time", ""),
        })
    return JsonResponse({"results": results}, json_dumps_params={"ensure_ascii": False})


@require_GET
def fivepost_delivery_cost_api(request):
    """
    Расчёт стоимости доставки 5post по городу (тариф по зоне).
    GET /api/fivepost/delivery-cost/?city=Москва&weight=1000
    Ответ: {"ok": true, "city": "Москва", "zone": 1, "price": 187, "delivery_days": 3}
    """
    city_name = (request.GET.get("city") or "").strip()
    if not city_name:
        return JsonResponse(
            {"ok": False, "error": "Укажите параметр city."},
            status=400,
        )
    try:
        weight = int(request.GET.get("weight", 1000))
        weight = max(500, min(weight, 30000))
    except (TypeError, ValueError):
        weight = 1000
    result = fivepost_get_delivery_cost(city_name, weight, amount=0, payment_prepaid=True)
    if not result:
        return JsonResponse(
            {"ok": False, "error": "Не удалось рассчитать доставку 5post."},
            json_dumps_params={"ensure_ascii": False},
            status=502,
        )
    return JsonResponse({
        "ok": True,
        "city": city_name,
        "zone": result.get("zone", 1),
        "price": result.get("price", 0),
        "delivery_days": result.get("delivery_days", 0),
    }, json_dumps_params={"ensure_ascii": False})


@require_GET
def fivepost_pvz_api(request):
    """
    Список ПВЗ 5post по городу (по названию).
    GET /api/fivepost/pvz/?city=Москва → {"results": [{"id": "uuid", "code": "...", "name": "...", "address": "..."}, ...]}
    """
    city_name = (request.GET.get("city") or "").strip()
    if not city_name:
        return JsonResponse({"results": []}, json_dumps_params={"ensure_ascii": False})
    results = get_pvz_by_city(city_name, max_results=50)
    return JsonResponse({"results": results}, json_dumps_params={"ensure_ascii": False})


@require_GET
def russianpost_delivery_cost_api(request):
    """
    Расчёт стоимости доставки Почтой России по индексу получателя (tariff.pochta.ru).
    GET /api/russianpost/delivery-cost/?to_index=190000&weight=1000&sumoc=100
    Ответ: {"ok": true, "to_index": 190000, "price": 333.64, "delivery_days": null, "name": "..."}
    """
    to_index_raw = (request.GET.get("to_index") or "").strip()
    if not to_index_raw or len(to_index_raw) != 6 or not to_index_raw.isdigit():
        return JsonResponse(
            {"ok": False, "error": "Укажите 6-значный индекс получателя (to_index)."},
            status=400,
        )
    to_index = int(to_index_raw)
    from_index = getattr(settings, "RUSSIANPOST_SENDER_INDEX", None)
    if not from_index:
        return JsonResponse(
            {"ok": False, "error": "Не настроен RUSSIANPOST_SENDER_INDEX в .env."},
            json_dumps_params={"ensure_ascii": False},
            status=503,
        )
    try:
        weight = int(request.GET.get("weight", 1000))
        weight = max(1, min(weight, 20000))
    except (TypeError, ValueError):
        weight = 1000
    try:
        sumoc = float(request.GET.get("sumoc", 100))
        sumoc = max(0.01, min(sumoc, 3000000))
    except (TypeError, ValueError):
        sumoc = 100

    result = russianpost_get_delivery_cost(from_index, to_index, weight, sumoc_rub=sumoc)
    if not result:
        return JsonResponse(
            {"ok": False, "error": "Не удалось рассчитать тариф Почты России."},
            json_dumps_params={"ensure_ascii": False},
            status=502,
        )
    return JsonResponse({
        "ok": True,
        "to_index": to_index,
        "price": result.get("price", 0),
        "delivery_days": result.get("delivery_days"),
        "name": result.get("name", "Почта России"),
    }, json_dumps_params={"ensure_ascii": False})


@require_GET
def cities_autocomplete_api(request):
    """
    Подсказки городов для поля «Город» при оформлении заказа.
    GET /api/cities/?q=моск → {"results": ["Москва", "Московский", ...]}
    """
    q = (request.GET.get("q") or "").strip()
    if not q:
        return JsonResponse({"results": []})
    qs = City.objects.filter(name__icontains=q).order_by("name").values_list("name", flat=True)[:20]
    return JsonResponse({"results": list(qs)}, json_dumps_params={"ensure_ascii": False})


def _require_order_api_key(request):
    """
    Если в настройках задан ORDER_SYNC_API_KEY — проверяем ключ в заголовке X-API-Key
    или в query-параметре X-API-Key (для удобства в Postman и др.).
    Возвращает None, если доступ разрешён, иначе JsonResponse с 401.
    """
    key = getattr(settings, "ORDER_SYNC_API_KEY", None)
    if not key:
        return None
    provided = (
        request.headers.get("X-API-Key")
        or request.META.get("HTTP_X_API_KEY")
        or request.GET.get("X-API-Key")
    )
    if provided != key:
        return JsonResponse(
            {"error": "unauthorized", "message": "Требуется заголовок X-API-Key."},
            status=401,
        )
    return None


def _parse_unix_timestamp(value: str):
    """
    Преобразует строку с Unix time (секунды) в aware datetime в UTC.
    Возвращает datetime или None, если формат неверный.
    """
    try:
        ts = int(value)
    except (TypeError, ValueError):
        return None
    # Всегда считаем, что Unix time передаётся в UTC
    return datetime.fromtimestamp(ts, tz=dt_timezone.utc)


@require_GET
def order_sync_queue_api(request):
    """
    API #1: список изменившихся заказов.

    Параметры:
    - since: Unix time (секунды, UTC). Если указан — берём записи с created_at >= since.

    Ответ:
    {
      "results": ["uuid1", "uuid2", ...]  # уникальные UUID заказов
    }
    """
    auth_error = _require_order_api_key(request)
    if auth_error:
        return auth_error
    since_raw = request.GET.get("since")
    qs = OrderSyncQueue.objects.filter(order_uuid__isnull=False)

    if since_raw:
        since_dt = _parse_unix_timestamp(since_raw)
        if not since_dt:
            return JsonResponse(
                {"error": "invalid_since", "message": "Параметр 'since' должен быть Unix time (целое число секунд)."},
                status=400,
            )
        qs = qs.filter(created_at__gte=since_dt)

    qs = qs.order_by("created_at").values_list("order_uuid", flat=True)

    uuids = []
    seen = set()
    for uid in qs:
        s = str(uid)
        if s not in seen:
            seen.add(s)
            uuids.append(s)

    return JsonResponse({"results": uuids}, json_dumps_params={"ensure_ascii": False})


def _order_queryset_optimized():
    """Заказ с подтянутыми user, delivery_method и items→variant→product (минимум запросов к БД)."""
    return Order.objects.select_related("user", "delivery_method").prefetch_related(
        "items__variant__product"
    )


@require_GET
def order_detail_api(request, order_uuid):
    """
    API #2: детали заказа по UUID.

    URL: /api/orders/<uuid>/

    Ответ:
    {
      "uuid": "...",
      "number": 100001,
      ... (остальные поля из payload)
    }
    """
    auth_error = _require_order_api_key(request)
    if auth_error:
        return auth_error
    order = get_object_or_404(_order_queryset_optimized(), uuid=order_uuid)
    payload = _order_to_payload(order)
    payload_with_uuid = {"uuid": str(order.uuid)}
    payload_with_uuid.update(payload)
    return JsonResponse(payload_with_uuid, json_dumps_params={"ensure_ascii": False})


# Максимум заказов в одном batch-запросе (чтобы не перегружать ответ)
ORDER_BATCH_MAX = 100


@require_GET
def order_detail_batch_api(request):
    """
    API #2b: детали нескольких заказов за один запрос (ускоряет выгрузку).

    GET /api/orders/batch/?uuids=uuid1,uuid2,uuid3
    Ответ: {"results": [{ "uuid": "...", ... }, ...]}

    Параметр uuids — через запятую, до ORDER_BATCH_MAX штук.
    """
    auth_error = _require_order_api_key(request)
    if auth_error:
        return auth_error
    uuids_raw = (request.GET.get("uuids") or "").strip()
    if not uuids_raw:
        return JsonResponse(
            {"error": "missing_uuids", "message": "Укажите параметр uuids (через запятую)."},
            status=400,
        )
    uuids = [u.strip() for u in uuids_raw.split(",") if u.strip()][:ORDER_BATCH_MAX]
    if not uuids:
        return JsonResponse({"results": []}, json_dumps_params={"ensure_ascii": False})

    orders = list(
        _order_queryset_optimized().filter(uuid__in=uuids)
    )
    order_by_uuid = {str(o.uuid): o for o in orders}
    results = []
    for uid in uuids:
        order = order_by_uuid.get(uid)
        if not order:
            continue
        payload = _order_to_payload(order)
        payload_with_uuid = {"uuid": str(order.uuid)}
        payload_with_uuid.update(payload)
        results.append(payload_with_uuid)

    return JsonResponse({"results": results}, json_dumps_params={"ensure_ascii": False})


@require_GET
def cdek_delivery_cost_api(request):
    """
    Расчёт стоимости доставки СДЭК по городу получателя.

    GET /api/cdek/delivery-cost/?city=Москва&weight=1000

    Параметры:
    - city: название города (обязательно)
    - weight: вес в граммах (опционально, по умолчанию 1000)

    Ответ:
    {
      "ok": true,
      "city": "Москва",
      "city_code": 44,
      "weight_grams": 1000,
      "tariffs": [
        {"tariff_code": 136, "name": "Посылка склад-склад", "delivery_sum": 185, "period_min": 1, "period_max": 2},
        ...
      ]
    }
    """
    city_name = (request.GET.get("city") or "").strip()
    city_code_param = request.GET.get("city_code")
    if not city_name and not city_code_param:
        return JsonResponse(
            {"ok": False, "error": "Укажите параметр city или city_code."},
            status=400,
        )

    try:
        weight = int(request.GET.get("weight", 1000))
        weight = max(500, min(weight, 30000))
    except (TypeError, ValueError):
        weight = 1000

    # Город получателя: по city_code или ищем по названию в справочнике СДЭК
    if city_code_param:
        try:
            to_code = int(city_code_param)
            to_city = {"city": city_name or str(to_code), "code": to_code}
        except (TypeError, ValueError):
            to_code = None
            to_city = None
    else:
        cities = get_cities(country_code="RU", name_filter=city_name)
        if not cities:
            return JsonResponse(
                {"ok": False, "error": f"Город «{city_name}» не найден в справочнике СДЭК."},
                json_dumps_params={"ensure_ascii": False},
                status=404,
            )
        to_city = cities[0]
        to_code = int(to_city["code"])

    # Город отправления: из настроек или Москва
    from_code = getattr(settings, "CDEK_SENDER_CITY_CODE", None)
    if from_code is None:
        from_code = 44

    result = get_delivery_cost(
        from_city_code=from_code,
        to_city_code=to_code,
        weight_grams=weight,
        length_cm=20,
        width_cm=15,
        height_cm=10,
    )
    if not result:
        return JsonResponse(
            {"ok": False, "error": "Не удалось рассчитать доставку. Попробуйте позже."},
            json_dumps_params={"ensure_ascii": False},
            status=502,
        )

    items = result.get("tariff_codes") or []
    raw = []
    for t in items:
        mode_val = t.get("delivery_mode") or t.get("mode")
        try:
            mode_int = int(mode_val) if mode_val is not None else None
        except (TypeError, ValueError):
            mode_int = None
        raw.append({
            "tariff_code": t.get("tariff_code"),
            "name": t.get("tariff_name", ""),
            "delivery_sum": float(t.get("delivery_sum", 0)),
            "period_min": int(t.get("period_min", 0)),
            "period_max": int(t.get("period_max", 0)),
            "delivery_mode": mode_int,
        })

    # Исключаем невыгодные тарифы (Сборный груз — LTL для юрлиц)
    exclude_names = ("сборный груз",)
    filtered = [t for t in raw if not any(
        ex in (t.get("name") or "").lower() for ex in exclude_names
    )]

    # Убираем дубликаты по (shortName, period): оставляем только самый дешёвый
    def _short_name(name: str) -> str:
        s = (name or "").lower()
        for p in ("дверь-дверь", "склад-склад", "дверь-склад", "склад-дверь"):
            s = s.replace(p, "").strip()
        s = re.sub(r"\s*до\s+\d+\s*$", "", s, flags=re.I).strip()
        return s or "доставка"

    seen: dict = {}
    for t in filtered:
        mode = t.get("delivery_mode")
        key = (_short_name(t["name"]), t["period_min"], t["period_max"], mode)
        if key not in seen or t["delivery_sum"] < seen[key]["delivery_sum"]:
            seen[key] = t
    tariffs = sorted(seen.values(), key=lambda x: x["delivery_sum"])

    payload = {
        "ok": True,
        "city": to_city.get("city", city_name),
        "city_code": to_code,
        "weight_grams": weight,
        "tariffs": tariffs,
    }
    if request.GET.get("debug"):
        mode1 = [t for t in tariffs if t.get("delivery_mode") == 1]
        mode4 = [t for t in tariffs if t.get("delivery_mode") == 4]
        payload["_debug"] = {
            "raw_count": len(raw),
            "after_exclude": len(filtered),
            "after_dedup": len(tariffs),
            "mode_1_courier": len(mode1),
            "mode_4_pvz": len(mode4),
            "raw_by_mode": {
                1: [{"name": t["name"], "sum": t["delivery_sum"]} for t in raw if t.get("delivery_mode") == 1],
                4: [{"name": t["name"], "sum": t["delivery_sum"]} for t in raw if t.get("delivery_mode") == 4],
            },
        }
    return JsonResponse(payload, json_dumps_params={"ensure_ascii": False})
