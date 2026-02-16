from datetime import datetime, timezone as dt_timezone

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from .models import City, Order, OrderSyncQueue
from .sync_queue import _order_to_payload


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
