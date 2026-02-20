"""
URL configuration for store project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from orders.views import (
    cities_autocomplete_api,
    cdek_cities_api,
    cdek_delivery_cost_api,
    cdek_diagnostic_api,
    cdek_pvz_api,
    cdek_refresh_token_api,
    cdek_status_api,
    fivepost_delivery_cost_api,
    fivepost_pvz_api,
    order_detail_api,
    order_detail_batch_api,
    order_sync_queue_api,
    russianpost_delivery_cost_api,
)
from users.api_sync import (
    user_detail_api,
    user_detail_batch_api,
    user_sync_queue_api,
)

urlpatterns = [
    path("backend/", admin.site.urls),
    path("account/", include("users.urls")),
    path("catalog/", include("catalog.urls")),
    path("policy/", RedirectView.as_view(url="/catalog/policy/", permanent=True)),
    # API #1: список UUID заказов (с слешем и без — чтобы не было 301 редиректа)
    path("api/order-sync/", order_sync_queue_api, name="order_sync_queue_api"),
    path("api/order-sync", order_sync_queue_api, name="order_sync_queue_api_no_slash"),
    # API #1: список UUID пользователей
    path("api/user-sync/", user_sync_queue_api, name="user_sync_queue_api"),
    path("api/user-sync", user_sync_queue_api, name="user_sync_queue_api_no_slash"),
    # API #2b: пачка заказов за один запрос (быстрее для выгрузки)
    path("api/orders/batch/", order_detail_batch_api, name="order_detail_batch_api"),
    path("api/orders/batch", order_detail_batch_api, name="order_detail_batch_api_no_slash"),
    # API #2b: пачка пользователей за один запрос
    path("api/users/batch/", user_detail_batch_api, name="user_detail_batch_api"),
    path("api/users/batch", user_detail_batch_api, name="user_detail_batch_api_no_slash"),
    # API #2: детали заказа по UUID
    path("api/orders/<uuid:order_uuid>/", order_detail_api, name="order_detail_api"),
    path("api/orders/<uuid:order_uuid>", order_detail_api, name="order_detail_api_no_slash"),
    # API #2: детали пользователя по UUID (uuid + referred_by_uuid для дерева)
    path("api/users/<uuid:user_uuid>/", user_detail_api, name="user_detail_api"),
    path("api/users/<uuid:user_uuid>", user_detail_api, name="user_detail_api_no_slash"),
    # Подсказки городов
    path("api/cities/", cities_autocomplete_api, name="cities_autocomplete_api"),
    path("api/cities", cities_autocomplete_api, name="cities_autocomplete_api_no_slash"),
    # СДЭК: города, ПВЗ, расчёт доставки
    path("api/cdek/status/", cdek_status_api, name="cdek_status_api"),
    path("api/cdek/diagnostic/", cdek_diagnostic_api, name="cdek_diagnostic_api"),
    path("api/cdek/refresh-token/", cdek_refresh_token_api, name="cdek_refresh_token_api"),
    path("api/cdek/cities/", cdek_cities_api, name="cdek_cities_api"),
    path("api/cdek/cities", cdek_cities_api, name="cdek_cities_api_no_slash"),
    path("api/cdek/pvz/", cdek_pvz_api, name="cdek_pvz_api"),
    path("api/cdek/pvz", cdek_pvz_api, name="cdek_pvz_api_no_slash"),
    path("api/cdek/delivery-cost/", cdek_delivery_cost_api, name="cdek_delivery_cost_api"),
    path("api/cdek/delivery-cost", cdek_delivery_cost_api, name="cdek_delivery_cost_api_no_slash"),
    # 5post: расчёт доставки, ПВЗ по городу
    path("api/fivepost/delivery-cost/", fivepost_delivery_cost_api, name="fivepost_delivery_cost_api"),
    path("api/fivepost/delivery-cost", fivepost_delivery_cost_api, name="fivepost_delivery_cost_api_no_slash"),
    path("api/fivepost/pvz/", fivepost_pvz_api, name="fivepost_pvz_api"),
    path("api/fivepost/pvz", fivepost_pvz_api, name="fivepost_pvz_api_no_slash"),
    # Почта России: расчёт по индексу получателя (tariff.pochta.ru)
    path("api/russianpost/delivery-cost/", russianpost_delivery_cost_api, name="russianpost_delivery_cost_api"),
    path("api/russianpost/delivery-cost", russianpost_delivery_cost_api, name="russianpost_delivery_cost_api_no_slash"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
