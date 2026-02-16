"""Очередь выгрузки заказов."""
from django.db import transaction

from .models import Order, OrderSyncQueue


def _order_to_payload(order):
    items_data = []
    for oi in order.items.select_related("variant__product").all():
        items_data.append({
            "variant_id": oi.variant_id,
            "product": oi.variant.product.name if oi.variant.product_id else None,
            "quantity": oi.quantity,
            "price": str(oi.price),
            "pv": str(getattr(oi, "pv", 0) or 0),
            "line_pv": str(getattr(oi, "line_pv", 0) or 0),
        })
    return {
        "number": order.number,
        "user_uuid": str(order.user.uuid) if order.user_id else None,
        "name": order.name,
        "email": order.email,
        "phone": order.phone or "",
        "delivery_method": order.delivery_method.code if order.delivery_method_id else None,
        "delivery_city": order.delivery_city or "",
        "delivery_address": order.delivery_address or "",
        "payment_type": order.payment_type,
        "total": str(order.total),
        "total_pv": str(getattr(order, "total_pv", 0) or 0),
        "status": order.status,
        "comment": order.comment or "",
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "items": items_data,
    }


def enqueue_order_sync(action, order=None, *, order_uuid=None, payload=None):
    with transaction.atomic():
        if action == "delete":
            uid = order_uuid if order_uuid is not None else (order.uuid if order else None)
            payload = payload or {"action": "delete"}
            OrderSyncQueue.objects.create(
                action=OrderSyncQueue.Action.DELETE,
                order_uuid=uid,
                payload=payload,
            )
        else:
            if not order:
                return
            payload = payload or _order_to_payload(order)
            OrderSyncQueue.objects.create(
                action=OrderSyncQueue.Action.CREATE if action == "create" else OrderSyncQueue.Action.UPDATE,
                order_uuid=order.uuid,
                payload=payload,
            )
