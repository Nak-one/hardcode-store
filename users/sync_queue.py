"""
Очередь выгрузки пользователей: формирование payload и постановка в очередь.
"""
from django.db import transaction

from .models import User, UserSyncQueue


def _user_to_payload(user):
    """Собрать JSON для выгрузки пользователя (create/update)."""
    return {
        "uuid": str(user.uuid),
        "email": user.email,
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
        "phone": user.phone or "",
        "is_business_user": user.is_business_user,
        "referred_by_uuid": str(user.referred_by.uuid) if user.referred_by_id else None,
        "is_active": user.is_active,
        "date_joined": user.date_joined.isoformat() if user.date_joined else None,
    }


def enqueue_user_sync(action, user=None, *, user_uuid=None, payload=None):
    """
    Поставить в очередь запись на выгрузку.

    :param action: 'create' | 'update' | 'delete'
    :param user: экземпляр User (для create/update); для delete передать до удаления (оттуда возьмём uuid)
    :param user_uuid: UUID пользователя (для delete можно передать вместо user после удаления из БД)
    :param payload: готовый dict (опционально; если не передан, для create/update строится из user)
    """
    with transaction.atomic():
        if action == "delete":
            uid = user_uuid if user_uuid is not None else (user.uuid if user else None)
            uid_str = str(uid) if uid else None
            payload = payload or {"uuid": uid_str, "action": "delete"}
            UserSyncQueue.objects.create(
                action=UserSyncQueue.Action.DELETE,
                user_uuid=uid,
                payload=payload,
            )
        else:
            if not user:
                return
            payload = payload or _user_to_payload(user)
            UserSyncQueue.objects.create(
                action=UserSyncQueue.Action.CREATE if action == "create" else UserSyncQueue.Action.UPDATE,
                user_uuid=user.uuid,
                payload=payload,
            )
