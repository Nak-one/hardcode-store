from django.urls import path

from . import views

app_name = "users"

urlpatterns = [
    path("", views.cabinet_view, name="cabinet"),
    path("profile/", views.profile_edit_view, name="profile"),
    path("password/", views.password_change_view, name="password_change"),
    path("referral/", views.referral_view, name="referral"),
    path("business/", views.business_join_view, name="business_join"),
    path("orders/", views.orders_list_view, name="orders_list"),
    path("orders/<int:order_id>/", views.order_detail_view, name="order_detail"),
    path("addresses/", views.address_list_view, name="address_list"),
    path("addresses/add/", views.address_create_view, name="address_add"),
    path("addresses/<int:pk>/edit/", views.address_edit_view, name="address_edit"),
    path("addresses/<int:pk>/delete/", views.address_delete_view, name="address_delete"),
    path("addresses/<int:pk>/default/", views.address_set_default_view, name="address_set_default"),
    path("register/", views.register_view, name="register"),
    path("register/<uuid:ref>/", views.register_with_ref_redirect, name="register_with_ref"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
]
