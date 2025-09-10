from django.urls import path
from . import api_views

urlpatterns = [
    path('', api_views.payment_list, name='payment_list'),
    path('<int:payment_id>/', api_views.payment_detail, name='payment_detail'),
    path('initiate/', api_views.initiate_payment, name='initiate_payment'),
    path('status/<str:transaction_id>/', api_views.payment_status, name='payment_status'),
    path('refund/<str:transaction_id>/', api_views.refund_payment, name='refund_payment'),
]
