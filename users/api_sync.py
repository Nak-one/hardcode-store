"""
API выгрузки пользователей для внешнего сервиса (дерево пользователей).

Аналогично API заказов:
1. GET /api/user-sync/ — список UUID пользователей из очереди изменений
2. GET /api/users/<uuid>/ — полные данные пользователя по UUID
3. GET /api/users/batch/?uuids=... — пачка пользователей за один запрос

Ключевые поля для построения дерева: uuid (пользователь) и referred_by_uuid (наставник).
"""
from datetime import datetime, timezone as dt_timezone

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from .models import User, UserSyncQueue
from .sync_queue import _user_to_payload


def _require_user_api_key(request):
    """
    Если в настройках задан USER_SYNC_API_KEY — проверяем ключ в заголовке X-API-Key
    или в query-параметре X-API-Key.
    """
    key = getattr(settings, "USER_SYNC_API_KEY", None)
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
    """Преобразует Unix time (секунды) в aware datetime в UTC."""
    try:
        ts = int(value)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(ts, tz=dt_timezone.utc)


@require_GET
def user_sync_queue_api(request):
    """
    API #1: список UUID пользователей из очереди изменений.

    Параметры:
    - since: Unix time (секунды, UTC). Если указан — записи с created_at >= since.

    Ответ:
    {
      "results": ["uuid1", "uuid2", ...]
    }
    """
    auth_error = _require_user_api_key(request)
    if auth_error:
        return auth_error
    since_raw = request.GET.get("since")
    qs = UserSyncQueue.objects.filter(user_uuid__isnull=False)

    if since_raw:
        since_dt = _parse_unix_timestamp(since_raw)
        if not since_dt:
            return JsonResponse(
                {"error": "invalid_since", "message": "Параметр 'since' должен быть Unix time (целое число секунд)."},
                status=400,
            )
        qs = qs.filter(created_at__gte=since_dt)

    qs = qs.order_by("created_at").values_list("user_uuid", flat=True)

    uuids = []
    seen = set()
    for uid in qs:
        s = str(uid)
        if s not in seen:
            seen.add(s)
            uuids.append(s)

    return JsonResponse({"results": uuids}, json_dumps_params={"ensure_ascii": False})


def _user_queryset_optimized():
    """User с подтянутым referred_by для минимума запросов."""
    return User.objects.select_related("referred_by")


@require_GET
def user_detail_api(request, user_uuid):
    """
    API #2: детали пользователя по UUID.

    URL: /api/users/<uuid>/

    Ключевые поля для построения дерева:
    - uuid: UUID пользователя
    - referred_by_uuid: UUID наставника (кто пригласил по реф-ссылке), null если нет

    Ответ:
    {
      "uuid": "...",
      "referred_by_uuid": "..." | null,
      "email": "...",
      ...
    }
    """
    auth_error = _require_user_api_key(request)
    if auth_error:
        return auth_error
    user = get_object_or_404(_user_queryset_optimized(), uuid=user_uuid)
    payload = _user_to_payload(user)
    # Явно выделяем ключевую связку для дерева
    result = {
        "uuid": str(user.uuid),
        "referred_by_uuid": str(user.referred_by.uuid) if user.referred_by_id else None,
    }
    result.update(payload)
    return JsonResponse(result, json_dumps_params={"ensure_ascii": False})


USER_BATCH_MAX = 100


@require_GET
def user_detail_batch_api(request):
    """
    API #2b: детали нескольких пользователей за один запрос.

    GET /api/users/batch/?uuids=uuid1,uuid2,uuid3
    Ответ: {"results": [{ "uuid": "...", "referred_by_uuid": "...", ... }, ...]}

    Параметр uuids — через запятую, до USER_BATCH_MAX штук.
    """
    auth_error = _require_user_api_key(request)
    if auth_error:
        return auth_error
    uuids_raw = (request.GET.get("uuids") or "").strip()
    if not uuids_raw:
        return JsonResponse(
            {"error": "missing_uuids", "message": "Укажите параметр uuids (через запятую)."},
            status=400,
        )
    uuids = [u.strip() for u in uuids_raw.split(",") if u.strip()][:USER_BATCH_MAX]
    if not uuids:
        return JsonResponse({"results": []}, json_dumps_params={"ensure_ascii": False})

    users = list(_user_queryset_optimized().filter(uuid__in=uuids))
    user_by_uuid = {str(u.uuid): u for u in users}
    results = []
    for uid in uuids:
        user = user_by_uuid.get(uid)
        if not user:
            continue
        payload = _user_to_payload(user)
        result = {
            "uuid": str(user.uuid),
            "referred_by_uuid": str(user.referred_by.uuid) if user.referred_by_id else None,
        }
        result.update(payload)
        results.append(result)

    return JsonResponse({"results": results}, json_dumps_params={"ensure_ascii": False})
