"""
Authentication app URLs
apps/authentication/urls.py
"""
from django.urls import path
from . import views

# Import views from other apps
from apps.menu import views as menu_views
from apps.orders import views as orders_views
from apps.notifications import views as notifications_views
from apps.payments import views as payments_views
from apps.reports import views as reports_views

app_name = 'auth'

# Main authentication URLs
urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("contact-admin-reset/", views.contact_admin_reset, name="contact_admin_reset"),
]

# Employee URLs
employee_urlpatterns = [
    path('dashboard/', views.EmployeeDashboardView.as_view(), name='dashboard'),
    path('refresh-orders/', views.refresh_employee_orders, name='refresh_orders'),
    path('menu/', menu_views.employee_menu, name='menu'),
    path('place-order/', orders_views.place_order, name='place_order'),
    path('order-history/', orders_views.order_history, name='order_history'),
    # Changed from employee_notifications to notifications_list (the actual function that exists)
    path('notifications/', notifications_views.notifications_list, name='notifications'),
    path('add-to-cart/', orders_views.add_to_cart, name='add_to_cart'),
    path('quick-order/', orders_views.quick_order, name='quick_order'),
    path('process-topup/', payments_views.process_topup, name='process_topup'),
    # path("contact-admin-reset/", views.contact_admin_reset, name="contact_admin_reset"),
]

# Canteen Admin URLs
canteen_admin_urlpatterns = [
    path('dashboard/', views.CanteenAdminDashboardView.as_view(), name='dashboard'),
    path('menu-management/', menu_views.menu_management, name='menu_management'),
    path('orders-management/', orders_views.orders_management, name='orders_management'),
    path('inventory/', menu_views.inventory_management, name='inventory'),
    # You may need to create this view or use an existing one like send_system_notification
    path('notifications/create/', notifications_views.send_system_notification, name='notifications_create'),
    path('reports/', reports_views.canteen_admin_reports, name='reports'),
    path('dashboard-data/', views.canteen_admin_dashboard_data, name='dashboard_data'),
    path('order-queue/', orders_views.order_queue, name='order_queue'),
    path('update-order-status/', orders_views.update_order_status, name='update_order_status'),
    path('add-menu-item/', menu_views.add_menu_item, name='add_menu_item'),
    # path('generate-daily-report/', reports_views.generate_daily_report, name='generate_daily_report'),
]

# System Admin URLs
system_admin_urlpatterns = [
    path('dashboard/', views.SystemAdminDashboardView.as_view(), name='dashboard'),
    path('users/', views.SystemAdminDashboardView.as_view(), name='users'),  # Same as dashboard
    path('system-config/', views.system_config, name='system_config'),
    path('analytics/', reports_views.system_admin_reports, name='analytics'),
    # path('audit-logs/', views.audit_logs, name='audit_logs'),
]

# Include role-specific URLs with namespace
employee_urls = (employee_urlpatterns, 'employee')
canteen_admin_urls = (canteen_admin_urlpatterns, 'canteen_admin')
system_admin_urls = (system_admin_urlpatterns, 'system_admin')