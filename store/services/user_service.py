"""
User service: abstraction over user storage.
Uses Django auth (get_user_model()) now; can be replaced by API client later.
"""
from django.contrib.auth import get_user_model, authenticate as django_authenticate


def get_current_user_id(request):
    """Return current user pk or None."""
    if request.user.is_authenticated:
        return request.user.pk
    return None


def get_user_by_id(user_id):
    """Return User instance by pk or None."""
    if user_id is None:
        return None
    User = get_user_model()
    try:
        return User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return None


def get_user_by_uuid(value):
    """Return User instance by uuid or None."""
    if not value or not str(value).strip():
        return None
    User = get_user_model()
    try:
        return User.objects.get(uuid=str(value).strip())
    except User.DoesNotExist:
        return None


def extract_uuid_from_ref(ref_string):
    """
    Из строки извлекает UUID: поддерживает голый UUID или URL с ?ref=UUID.
    Возвращает строку UUID или None.
    """
    from urllib.parse import urlparse, parse_qs
    if not ref_string or not (s := str(ref_string).strip()):
        return None
    if "ref=" in s or "?" in s:
        try:
            parsed = urlparse(s)
            qs = parse_qs(parsed.query)
            refs = qs.get("ref", qs.get("REF", []))
            if refs and refs[0].strip():
                return refs[0].strip()
        except Exception:
            pass
    return s


def create_user(*, email, password, referred_by=None, **extra_fields):
    """
    Create a new user. USERNAME_FIELD is assumed to be 'email'.
    referred_by: User instance or None. Если указан — новый пользователь сразу становится бизнес-пользователем.
    """
    User = get_user_model()
    user = User(email=email, **extra_fields)
    user.set_password(password)
    if referred_by is not None:
        user.referred_by = referred_by
        user.is_business_user = True
    user.save()
    return user


def authenticate(request, email=None, password=None):
    """Authenticate by email/password. Returns User or None."""
    return django_authenticate(request, username=email, password=password)
