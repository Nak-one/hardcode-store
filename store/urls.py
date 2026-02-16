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
    order_detail_api,
    order_detail_batch_api,
    order_sync_queue_api,
)

urlpatterns = [
    path("backend/", admin.site.urls),
    path("account/", include("users.urls")),
    path("catalog/", include("catalog.urls")),
    path("policy/", RedirectView.as_view(url="/catalog/policy/", permanent=True)),
    # API #1: список UUID (с слешем и без — чтобы не было 301 редиректа)
    path("api/order-sync/", order_sync_queue_api, name="order_sync_queue_api"),
    path("api/order-sync", order_sync_queue_api, name="order_sync_queue_api_no_slash"),
    # API #2b: пачка заказов за один запрос (быстрее для выгрузки)
    path("api/orders/batch/", order_detail_batch_api, name="order_detail_batch_api"),
    path("api/orders/batch", order_detail_batch_api, name="order_detail_batch_api_no_slash"),
    # API #2: детали заказа по UUID
    path("api/orders/<uuid:order_uuid>/", order_detail_api, name="order_detail_api"),
    path("api/orders/<uuid:order_uuid>", order_detail_api, name="order_detail_api_no_slash"),
    # Подсказки городов
    path("api/cities/", cities_autocomplete_api, name="cities_autocomplete_api"),
    path("api/cities", cities_autocomplete_api, name="cities_autocomplete_api_no_slash"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
