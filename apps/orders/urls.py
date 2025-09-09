from django.urls import path
from . import views

urlpatterns = [
    # Employee endpoints
    path('place/', views.place_order, name='place_order'),
    path('cart/add/', views.add_to_cart, name='add_to_cart'),
    path('quick-order/', views.quick_order, name='quick_order'),
    path('history/', views.order_history, name='order_history'),
    path('cancel/<uuid:order_id>/', views.cancel_order, name='cancel_order'),

    # Canteen admin endpoints
    path('management/', views.orders_management, name='orders_management'),
    path('queue/', views.order_queue, name='order_queue'),
    path('update-status/', views.update_order_status, name='update_order_status'),

    # APIs
    path('api/details/<uuid:order_id>/', views.order_details_api, name='order_details_api'),
    path('api/reorder-items/', views.reorder_items_api, name='reorder_items_api'),
]
