from django.urls import path
from . import views

urlpatterns = [
    # Dashboards
    path('canteen-admin/', views.canteen_admin_reports, name='canteen_admin_reports'),
    path('system-admin/', views.system_admin_reports, name='system_admin_reports'),

    # Report generation
    # path('daily/generate/', views.generate_daily_report, name='generate_daily_report'),
    path('daily/download/<uuid:report_id>/', views.download_report, name='download_report'),
    # path('menu-performance/', views.menu_performance_report, name='menu_performance_report'),
    path('user-activity/', views.user_activity_report, name='user_activity_report'),

    # APIs
    # path('api/list/', views.reports_list_api, name='reports_list_api'),
    # path('api/dashboard/', views.dashboard_analytics_api, name='dashboard_analytics_api'),
]
