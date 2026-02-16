"""
Accounts service stub: balance, accounts, transfers, withdrawals.
Later can be replaced by call to external accounts API.
"""
from decimal import Decimal


def get_balance(user_id):
    """Return balance for user. Stub: always 0."""
    if user_id is None:
        return Decimal("0.00")
    return Decimal("0.00")


def get_accounts(user_id):
    """Return list of user accounts. Stub: 1-2 accounts with zero balance."""
    if user_id is None:
        return []
    return [
        {"id": 1, "name": "Основной счёт", "balance": "0.00", "currency": "RUB", "details": []},
        {"id": 2, "name": "Бонусный счёт", "balance": "0.00", "currency": "RUB", "details": []},
    ]


def get_transfers(user_id):
    """Return transfer history. Stub: empty list."""
    if user_id is None:
        return []
    return []


def get_withdrawals(user_id):
    """Return withdrawal requests history. Stub: empty list."""
    if user_id is None:
        return []
    return []
