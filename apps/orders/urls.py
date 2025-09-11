# apps/orders/urls.py
from django.urls import path
from . import views

app_name = "orders"

urlpatterns = [
    # Employee-facing
    path("place/", views.place_order, name="place"),                 # e.g. reverse('orders:place')
    path("place-order/", views.place_order, name="place_order"),     # alternate name used by other includes
    path("history/", views.order_history, name="history"),
    path("detail/<uuid:order_id>/", views.order_detail, name="detail"),
    path("quick-order/", views.quick_order, name="quick_order"),
    path("add-to-cart/", views.add_to_cart, name="add_to_cart"),
    path("process-topup/", views.process_topup, name="process_topup"),

    # Canteen admin
    path("manage/", views.orders_management, name="manage"),
    path("validate/<uuid:order_id>/", views.validate_order, name="validate"),
    path("cancel/<uuid:order_id>/", views.cancel_order, name="cancel"),

    # Payment continuation
    path("proceed-to-payment/<uuid:order_id>/", views.proceed_to_payment, name="proceed_to_payment"),
]
