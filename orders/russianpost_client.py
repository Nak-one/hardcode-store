"""
Клиент тарификатора Почты России (tariff.pochta.ru).
Расчёт стоимости доставки по индексам отправителя и получателя.
Документация: https://www.pochta.ru/support/business/api (блокируется по IP), описание параметров — в ответах API.
"""
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

from django.conf import settings

logger = logging.getLogger(__name__)

TARIFF_URL = "https://tariff.pochta.ru/tariff/v1/calculate"
# Код объекта: 4040 = посылка с объявленной ценностью и наложенным платежом (требует sumoc)
OBJECT_DEFAULT = 4040


def get_delivery_cost(
    from_index: int,
    to_index: int,
    weight_grams: int,
    sumoc_rub: float = 100.0,
    object_code: Optional[int] = None,
) -> Optional[dict]:
    """
    Расчёт стоимости доставки Почтой России через tariff.pochta.ru.
    from_index, to_index — 6-значные индексы; weight_grams — вес в граммах;
    sumoc_rub — объявленная ценность в руб. (для объекта 4040 минимум 0.01).
    Возвращает {"price": float, "delivery_days": int | None, "name": str} или None.
    """
    if not (100000 <= from_index <= 999999 and 100000 <= to_index <= 999999):
        logger.warning("Russian Post: неверный формат индексов from=%s to=%s", from_index, to_index)
        return None
    weight_grams = max(1, min(weight_grams, 20000))
    sumoc_rub = max(0.01, float(sumoc_rub))
    obj = object_code if object_code is not None else getattr(settings, "RUSSIANPOST_OBJECT", None) or OBJECT_DEFAULT

    base = getattr(settings, "RUSSIANPOST_TARIFF_URL", None) or TARIFF_URL
    params = {
        "from": from_index,
        "to": to_index,
        "object": obj,
        "weight": weight_grams,
        "sumoc": round(sumoc_rub, 2),
    }
    url = base + "?" + urllib.parse.urlencode(params)

    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as e:
        logger.warning("Russian Post tariff request error: %s", e)
        return None
    except json.JSONDecodeError as e:
        logger.warning("Russian Post tariff JSON error: %s", e)
        return None

    errors = data.get("errors") or data.get("error") or []
    if errors:
        logger.info("Russian Post tariff errors: %s", errors[:2])
        return None

    # Успех: сумма в поле pay (в копейках) или paynds (с НДС, в копейках)
    pay_kopecks = data.get("pay") or data.get("paynds")
    if pay_kopecks is None:
        logger.warning("Russian Post: не найдена сумма в ответе, ключи: %s", list(data.keys())[:20])
        return None
    price = float(pay_kopecks) / 100.0

    name = data.get("name") or data.get("typcatname") or "Почта России"
    # Срок доставки в ответе tariff.pochta.ru может не быть; при необходимости брать из справочников
    delivery_days = data.get("delivery_days") or data.get("days")
    return {
        "price": round(price, 2),
        "delivery_days": int(delivery_days) if delivery_days is not None else None,
        "name": name,
    }
