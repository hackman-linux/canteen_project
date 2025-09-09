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

# apps/notifications/urls.py
from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    # User notifications
    path('', views.notifications_list, name='notifications_list'),
    path('api/', views.notifications_api, name='notifications_api'),
    path('preferences/', views.notification_preferences, name='notification_preferences'),
    
    # Notification actions
    path('<uuid:notification_id>/read/', views.mark_notification_read, name='mark_notification_read'),
    path('<uuid:notification_id>/delete/', views.delete_notification, name='delete_notification'),
    path('mark-all-read/', views.mark_all_read, name='mark_all_read'),
    
    # Real-time notifications
    path('real-time/', views.get_real_time_notifications, name='get_real_time_notifications'),
    
    # System admin notifications
    path('system/', views.system_notification_management, name='system_notification_management'),
    path('system/send/', views.send_system_notification, name='send_system_notification'),
    path('system/templates/', views.notification_templates_api, name='notification_templates_api'),
    path('system/templates/create/', views.create_notification_template, name='create_notification_template'),
    path('stats/', views.notification_stats_api, name='notification_stats_api'),
]

# apps/reports/urls.py
from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    # Reports management
    path('', views.reports_management, name='reports_management'),
    path('list/', views.reports_list, name='reports_list'),
    path('<uuid:report_id>/', views.report_details, name='report_details'),
    path('<uuid:report_id>/download/', views.download_report, name='download_report'),
    path('<uuid:report_id>/delete/', views.delete_report, name='delete_report'),
    
    # Report generation
    path('generate/sales/', views.generate_sales_report, name='generate_sales_report'),
    path('generate/menu-performance/', views.generate_menu_performance_report, name='generate_menu_performance_report'),
    path('generate/user-activity/', views.generate_user_activity_report, name='generate_user_activity_report'),
    path('generate/financial/', views.generate_financial_report, name='generate_financial_report'),
    path('generate/inventory/', views.generate_inventory_report, name='generate_inventory_report'),
    path('generate/customer-analytics/', views.generate_customer_analytics, name='generate_customer_analytics'),
    path('generate/custom/', views.generate_custom_report, name='generate_custom_report'),
    path('generate/bulk/', views.bulk_report_generation, name='bulk_report_generation'),
    
    # Analytics and dashboards
    path('analytics/dashboard/', views.dashboard_analytics_api, name='dashboard_analytics_api'),
    path('stats/', views.reports_dashboard_stats, name='reports_dashboard_stats'),
    
    # Data export
    path('export/', views.export_data, name='export_data'),
    
    # System utilities
    path('system/health/', views.system_health_check, name='system_health_check'),
    path('scheduler/', views.report_scheduler_api, name='report_scheduler_api'),
]

# Updated apps/menu/urls.py (Enhanced)
from django.urls import path
from . import views

app_name = 'menu'

urlpatterns = [
    # Employee menu views
    path('', views.employee_menu, name='employee_menu'),
    path('search/', views.search_menu_items, name='search_menu_items'),
    
    # Menu item details and actions
    path('item/<uuid:item_id>/', views.menu_item_details, name='menu_item_details'),
    path('item/<uuid:item_id>/favorite/', views.toggle_favorite, name='toggle_favorite'),
    path('item/<uuid:item_id>/reviews/', views.menu_item_reviews, name='menu_item_reviews'),
    path('item/<uuid:item_id>/review/add/', views.add_menu_review, name='add_menu_review'),
    
    # Management views (Admin)
    path('management/', views.menu_management, name='menu_management'),
    path('inventory/', views.inventory_management, name='inventory_management'),
    
    # CRUD operations (Admin)
    path('item/add/', views.add_menu_item, name='add_menu_item'),
    path('item/<uuid:item_id>/update/', views.update_menu_item, name='update_menu_item'),
    path('item/<uuid:item_id>/delete/', views.delete_menu_item, name='delete_menu_item'),
    path('item/<uuid:item_id>/stock/', views.update_stock, name='update_stock'),
    
    # Categories
    path('categories/', views.menu_categories_api, name='menu_categories_api'),
    path('categories/create/', views.create_menu_category, name='create_menu_category'),
    
    # Daily menu
    path('daily/', views.daily_menu_api, name='daily_menu_api'),
]

# Main project urls.py updates
# enterprise_canteen/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Authentication
    path('auth/', include('apps.authentication.urls')),
    path('', RedirectView.as_view(url='/auth/dashboard/', permanent=False)),
    
    # Core applications
    path('menu/', include('apps.menu.urls')),
    path('orders/', include('apps.orders.urls')),
    path('payments/', include('apps.payments.urls')),
    path('notifications/', include('apps.notifications.urls')),
    path('reports/', include('apps.reports.urls')),
    
    # API endpoints
    path('api/', include([
        path('menu/', include('apps.menu.urls')),
        path('orders/', include('apps.orders.urls')),
        path('payments/', include('apps.payments.urls')),
        path('notifications/', include('apps.notifications.urls')),
        path('reports/', include('apps.reports.urls')),
    ])),
]

# Serve static files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Custom error handlers
handler404 = 'apps.authentication.views.custom_404'
handler500 = 'apps.authentication.views.custom_500'
handler403 = 'apps.authentication.views.custom_403'

