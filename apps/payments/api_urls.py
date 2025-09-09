from django.urls import path
from . import api_views  # you will create api_views.py

urlpatterns = [
    path('initiate/', api_views.initiate_payment, name='initiate_payment'),
    path('status/<str:transaction_id>/', api_views.payment_status, name='payment_status'),
    path('refund/<str:transaction_id>/', api_views.refund_payment, name='refund_payment'),
]
