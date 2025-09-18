# urls.py for orders app
from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    # Employee Order Management
    path('place-order/', views.place_order, name='place_order'),  # Step 1: Redirect to menu
    path('create-order/', views.create_order_from_cart, name='create_order_form'),  # Step 2: Show order form
    path('history/', views.order_history, name='history'),
    path('<uuid:order_id>/detail/', views.order_detail, name='order_detail'),
    
    # Cart Management (AJAX endpoints)
    path('cart/add/<uuid:item_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/update/', views.update_cart, name='update_cart'),
    path('cart/get/', views.get_cart, name='get_cart'),
    path('cart/count/', views.get_cart_count, name='get_cart_count'),
    path('cart/validate/', views.validate_cart, name='validate_cart'),
    path('cart/clear/', views.clear_cart, name='clear_cart'),
    path('admin/confirm/<uuid:order_id>/', views.confirm_order, name='confirm_order'),
    path('admin/update-status/<uuid:order_id>/', views.update_order_status, name='update_order_status'),
    path('admin/cancel/<uuid:order_id>/', views.cancel_order, name='cancel_order'),
    
    # Payment Flow
    path('<uuid:order_id>/payment/', views.proceed_to_payment, name='proceed_to_payment'),  # Step 5: Payment page
    
    # Canteen Admin Views
    path('manage/', views.orders_management, name='manage'),
    path('<uuid:order_id>/validate/', views.validate_order, name='validate_order'),
    path('<uuid:order_id>/cancel/', views.cancel_order, name='cancel_order'),
    
    # Legacy/Helper endpoints
    path('quick-order/', views.quick_order, name='quick_order'),
    path('quick-order/<uuid:item_id>/', views.quick_order, name='quick_order_item'),
    path('topup/', views.process_topup, name='process_topup'),  # Redirects to payments app
]

