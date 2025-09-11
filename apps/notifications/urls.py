from django.urls import path
from . import views

app_name = "notifications"

urlpatterns = [
    # User notifications
    path('', views.notifications_list, name='notifications_list'),
    path('mark_read/<uuid:notification_id>/', views.mark_notification_read, name='mark_notification_read'),
    path('mark-all-read/', views.mark_all_read, name='mark_all_read'),
    path('delete/<uuid:notification_id>/', views.delete_notification, name='delete_notification'),
    # path('api/', views.notifications_api, name='notifications_api'),
    path('preferences/', views.notification_preferences, name='notification_preferences'),
    path('real-time/', views.get_real_time_notifications, name='real_time'),
     path('stats/', views.notification_stats_api, name='stats_api'),


    # System notification management
    path('system/management/', views.system_notification_management, name='system_notification_management'),
    path('system/send/', views.send_system_notification, name='send_system_notification'),

    # Notification templates
#     path('api/templates/', views.notification_templates_api, name='notification_templates_api'),
#     path('api/templates/create/', views.create_notification_template, name='create_notification_template'),

#     # Real-time + stats
#     path('api/real-time/', views.get_real_time_notifications, name='get_real_time_notifications'),
#     path('api/stats/', views.notification_stats_api, name='notification_stats_api'),
]
