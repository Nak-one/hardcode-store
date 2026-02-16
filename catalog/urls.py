from django.urls import path
from . import views

app_name = "catalog"

urlpatterns = [
    path("", views.product_list, name="product_list"),
    path("category/<slug:category_slug>/", views.product_list, name="product_list_category"),
    path("product/<slug:slug>/", views.product_detail, name="product_detail"),
    path("product/<slug:slug>/quick/", views.product_quick_view, name="product_quick_view"),
    path("cart/", views.cart_view, name="cart"),
    path("cart/add/", views.cart_add, name="cart_add"),
    path("cart/remove/", views.cart_remove, name="cart_remove"),
    path("cart/remove-last/", views.cart_remove_last, name="cart_remove_last"),
    path("cart/set/", views.cart_set, name="cart_set"),
    path("cart/replace/", views.cart_replace, name="cart_replace"),
    path("checkout/", views.checkout_view, name="checkout"),
    path("order-success/<int:order_id>/", views.order_success_view, name="order_success"),
    path("favorites/", views.favorites_view, name="favorites"),
    path("favorites/toggle/<int:product_id>/", views.favorites_toggle, name="favorites_toggle"),
    path("policy/", views.policy_view, name="policy"),
]
