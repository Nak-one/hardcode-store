from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from store.services.user_service import (
    authenticate,
    create_user,
    extract_uuid_from_ref,
    get_user_by_uuid,
)

from .forms import LoginForm, ProfileForm, RegistrationForm


@require_http_methods(["GET"])
def register_with_ref_redirect(request, ref):
    """Реферальная ссылка: /account/register/<uuid>/ → страница регистрации с ?ref=uuid."""
    from django.urls import reverse
    url = reverse("users:register") + "?ref=" + str(ref)
    return redirect(url)


@require_http_methods(["GET", "POST"])
def register_view(request):
    """Registration. Supports ?ref=CODE in URL for referral link."""
    if request.user.is_authenticated:
        return redirect("catalog:product_list")

    ref_from_query = (request.GET.get("ref") or "").strip()
    initial = {}
    if ref_from_query:
        initial["ref_uuid"] = ref_from_query

    if request.method == "POST":
        form = RegistrationForm(request.POST, initial=initial)
        if form.is_valid():
            ref_uuid = form.cleaned_data.get("ref_uuid") or ref_from_query
            referred_by = get_user_by_uuid(ref_uuid) if ref_uuid else None
            user = create_user(
                email=form.cleaned_data["email"],
                password=form.cleaned_data["password1"],
                referred_by=referred_by,
            )
            auth_login(request, user)
            messages.success(request, "Регистрация прошла успешно.")
            return redirect("catalog:product_list")
    else:
        form = RegistrationForm(initial=initial)

    referrer = get_user_by_uuid(ref_from_query) if ref_from_query else None
    return render(
        request,
        "users/register.html",
        {
            "form": form,
            "ref_code": ref_from_query,
            "ref_from_link": bool(ref_from_query),
            "referrer_exists": referrer is not None,
            "referrer": referrer,
        },
    )


@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect("catalog:product_list")

    next_url = request.GET.get("next") or request.POST.get("next") or "catalog:product_list"

    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            user = authenticate(
                request,
                email=form.cleaned_data["email"],
                password=form.cleaned_data["password"],
            )
            if user is not None:
                auth_login(request, user)
                messages.success(request, "Вы вошли в аккаунт.")
                return redirect(request.POST.get("next") or next_url)
            form.add_error(None, "Неверный email или пароль.")
    else:
        form = LoginForm()

    return render(request, "users/login.html", {"form": form, "next": next_url})


@require_http_methods(["GET", "POST"])
def logout_view(request):
    auth_logout(request)
    messages.info(request, "Вы вышли из аккаунта.")
    return redirect("catalog:product_list")


@login_required
@require_http_methods(["GET"])
def cabinet_view(request):
    """Личный кабинет: обзор — приветствие и последние заказы."""
    from orders.models import Order

    last_orders = Order.objects.filter(user=request.user).select_related("delivery_method")[:5]
    return render(request, "users/cabinet.html", {"last_orders": last_orders})


@login_required
@require_http_methods(["GET"])
def orders_list_view(request):
    """Страница «Заказы»: полный список с фильтром и пагинацией."""
    from orders.models import Order

    qs = Order.objects.filter(user=request.user).select_related("delivery_method")
    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)
    paginator = Paginator(qs, 10)
    page = request.GET.get("page", "1")
    orders_page = paginator.get_page(page)
    return render(
        request,
        "users/orders_list.html",
        {"orders_page": orders_page, "status_filter": status_filter},
    )


@login_required
@require_http_methods(["GET"])
def order_detail_view(request, order_id):
    """Детальная страница заказа."""
    from orders.models import Order

    order = get_object_or_404(
        Order.objects.select_related("delivery_method").prefetch_related(
            "items__variant__product", "items__variant__attribute_values__attribute"
        ),
        pk=order_id,
        user=request.user,
    )
    return render(request, "users/order_detail.html", {"order": order})


@login_required
@require_http_methods(["GET", "POST"])
def profile_edit_view(request):
    """Редактирование профиля: имя, фамилия, телефон."""
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Профиль обновлён.")
            return redirect("users:profile")
    else:
        form = ProfileForm(instance=request.user)
    return render(request, "users/profile.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
def password_change_view(request):
    """Смена пароля."""
    from django.contrib.auth.forms import PasswordChangeForm

    if request.method == "POST":
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Пароль изменён.")
            return redirect("users:profile")
        messages.error(request, "Исправьте ошибки в форме.")
    else:
        form = PasswordChangeForm(request.user)
    return render(request, "users/password_change.html", {"form": form})


@login_required
@require_http_methods(["GET"])
def referral_view(request):
    """Реферальная программа перенесена в «Мой бизнес». Редирект со старых ссылок."""
    return redirect("users:business_join")


@login_required
@require_http_methods(["GET", "POST"])
def business_join_view(request):
    """
    Подключение как бизнес-пользователь.
    Пользователь должен указать реф-ссылку (или UUID наставника). Мы находим наставника,
    затем при подтверждении записываем его в «Приглашён пользователем» и включаем is_business_user.
    Отключить сам пользователь не может.
    """
    user = request.user
    if user.is_business_user:
        from store.services.accounts_service import get_accounts, get_transfers, get_withdrawals
        from store.services.referral_tree_service import get_referral_tree

        ref_link = request.build_absolute_uri(reverse("users:register_with_ref", kwargs={"ref": user.uuid}))
        return render(
            request,
            "users/business_join.html",
            {
                "already_business": True,
                "ref_link": ref_link,
                "accounts": get_accounts(user.pk),
                "transfers": get_transfers(user.pk),
                "withdrawals": get_withdrawals(user.pk),
                "referral_tree": get_referral_tree(user.pk),
            },
        )
    if request.method == "POST":
        ref_input = (request.POST.get("ref_link") or "").strip()
        confirm = request.POST.get("confirm") == "1"
        uuid_str = extract_uuid_from_ref(ref_input)
        referrer = get_user_by_uuid(uuid_str) if uuid_str else None
        if not ref_input:
            messages.error(request, "Укажите ссылку пригласившего или его UUID.")
        elif not referrer:
            messages.error(request, "По этой ссылке (или UUID) пользователь не найден. Проверьте данные.")
        elif referrer.pk == user.pk:
            messages.error(request, "Нельзя указать себя как наставника.")
        elif not referrer.is_business_user:
            messages.error(request, "Наставником может быть только бизнес-пользователь. Укажите ссылку пользователя с подключённым режимом «Бизнес с компанией».")
        elif not confirm:
            messages.error(request, "Подтвердите согласие.")
        else:
            user.referred_by = referrer
            user.is_business_user = True
            user.save(update_fields=["referred_by", "is_business_user"])
            messages.success(request, "Вы подключены как бизнес-пользователь. Наставник записан.")
            return redirect("users:business_join")
    return render(
        request,
        "users/business_join.html",
        {"already_business": False, "ref_link_value": request.POST.get("ref_link", "") if request.method == "POST" else ""},
    )


# ---------- Адреса доставки (Фаза 2) ----------


@login_required
@require_http_methods(["GET"])
def address_list_view(request):
    """Список сохранённых адресов."""
    addresses = request.user.addresses.all()
    return render(request, "users/address_list.html", {"addresses": addresses})


@login_required
@require_http_methods(["GET", "POST"])
def address_create_view(request):
    """Добавить адрес."""
    from .forms import UserAddressForm

    if request.method == "POST":
        form = UserAddressForm(request.POST, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Адрес добавлен.")
            return redirect("users:address_list")
    else:
        form = UserAddressForm(user=request.user)
    return render(request, "users/address_form.html", {"form": form, "title": "Новый адрес"})


@login_required
@require_http_methods(["GET", "POST"])
def address_edit_view(request, pk):
    """Редактировать адрес."""
    from .models import UserAddress
    from .forms import UserAddressForm

    addr = get_object_or_404(UserAddress, pk=pk, user=request.user)
    if request.method == "POST":
        form = UserAddressForm(request.POST, instance=addr, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Адрес обновлён.")
            return redirect("users:address_list")
    else:
        form = UserAddressForm(instance=addr, user=request.user)
    return render(request, "users/address_form.html", {"form": form, "title": "Редактировать адрес", "address": addr})


@login_required
@require_http_methods(["POST"])
def address_delete_view(request, pk):
    """Удалить адрес."""
    from .models import UserAddress

    addr = get_object_or_404(UserAddress, pk=pk, user=request.user)
    addr.delete()
    messages.success(request, "Адрес удалён.")
    return redirect("users:address_list")


@login_required
@require_http_methods(["POST"])
def address_set_default_view(request, pk):
    """Сделать адрес адресом по умолчанию."""
    from .models import UserAddress

    addr = get_object_or_404(UserAddress, pk=pk, user=request.user)
    request.user.addresses.update(is_default=False)
    addr.is_default = True
    addr.save()
    messages.success(request, "Адрес по умолчанию обновлён.")
    return redirect("users:address_list")
