"""
Referral tree service stub: tree of users who signed up via referral link.
Later can be replaced by call to external service.
"""


def get_referral_tree(user_id):
    """
    Return tree of referrals for user. Stub: empty structure.
    Expected format: {user: {...}, children: [...]}
    Each child has same structure for nested tree.
    """
    if user_id is None:
        return None
    return {"user": None, "children": []}
