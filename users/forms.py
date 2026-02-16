from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from .models import UserAddress

User = get_user_model()


class RegistrationForm(forms.Form):
    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={"autocomplete": "email", "placeholder": "email@example.com"}),
    )
    password1 = forms.CharField(
        label="Пароль",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "placeholder": "••••••••"}),
        min_length=8,
    )
    password2 = forms.CharField(
        label="Повторите пароль",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "placeholder": "••••••••"}),
    )
    ref_uuid = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
    )

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if email and User.objects.filter(email__iexact=email).exists():
            raise ValidationError("Пользователь с таким email уже зарегистрирован.")
        return email

    def clean(self):
        data = super().clean()
        if data.get("password1") != data.get("password2"):
            self.add_error("password2", "Пароли не совпадают.")
        return data


class LoginForm(forms.Form):
    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={"autocomplete": "email", "placeholder": "email@example.com"}),
    )
    password = forms.CharField(
        label="Пароль",
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password", "placeholder": "••••••••"}),
    )


class ProfileForm(forms.ModelForm):
    """Редактирование профиля: имя, фамилия, телефон."""

    class Meta:
        model = User
        fields = ("first_name", "last_name", "phone")
        labels = {"first_name": "Имя", "last_name": "Фамилия", "phone": "Телефон"}
        widgets = {
            "first_name": forms.TextInput(attrs={"placeholder": "Иван", "autocomplete": "given-name"}),
            "last_name": forms.TextInput(attrs={"placeholder": "Иванов", "autocomplete": "family-name"}),
            "phone": forms.TextInput(attrs={"placeholder": "+7 900 123-45-67", "autocomplete": "tel"}),
        }


class UserAddressForm(forms.ModelForm):
    """Форма адреса доставки."""

    class Meta:
        model = UserAddress
        fields = ("city", "address", "postal_code", "is_default")
        labels = {"city": "Город", "address": "Адрес", "postal_code": "Индекс", "is_default": "Использовать по умолчанию"}
        widgets = {
            "city": forms.TextInput(attrs={"placeholder": "Москва"}),
            "address": forms.Textarea(attrs={"rows": 2, "placeholder": "Улица, дом, квартира"}),
            "postal_code": forms.TextInput(attrs={"placeholder": "123456"}),
        }

    def __init__(self, user=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._user = user

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self._user:
            obj.user = self._user
        if commit:
            obj.save()
            if obj.is_default:
                UserAddress.objects.filter(user=obj.user).exclude(pk=obj.pk).update(is_default=False)
        return obj
