# apps/payments/urls.py
from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    # Payment processing
    path('process/', views.process_payment, name='process_payment'),
    path('topup/', views.process_topup, name='process_topup'),
    
    # Payment management
    path('history/', views.payment_history, name='payment_history'),
    path('verify/<uuid:payment_id>/', views.payment_verification, name='payment_verification'),
    path('wallet/dashboard/', views.wallet_dashboard, name='wallet_dashboard'),
    
    # Webhooks
    path('webhook/mtn/', views.mtn_webhook, name='mtn_webhook'),
    path('webhook/orange/', views.orange_webhook, name='orange_webhook'),
]