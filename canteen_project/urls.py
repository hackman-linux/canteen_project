from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth.decorators import login_required
from django.views.generic import RedirectView
from apps.authentication.views import DashboardRedirectView
from apps.authentication import urls as auth_urls
from django.conf.urls.i18n import i18n_patterns

urlpatterns = [
    # Admin interface
    path('admin/', admin.site.urls),
    
    # Authentication URLs
    path('auth/', include('apps.authentication.urls')),
    
    # Main dashboard redirect
    path('', RedirectView.as_view(url='/dashboard/', permanent=False)),
    path('dashboard/', login_required(DashboardRedirectView.as_view()), name='dashboard'),
    
    # App-specific URLs


    path('employee/', include(auth_urls.employee_urls)),
    path('canteen-admin/', include(auth_urls.canteen_admin_urls)),
    path('system-admin/', include(auth_urls.system_admin_urls)),

    
    # API URLs
    path('api/payments/', include('apps.payments.api_urls')),
    
    # Menu URLs
    path('menu/', include('apps.menu.urls')),
    
    # Orders URLs
    path('orders/', include('apps.orders.urls')),
    
    # Payments URLs
    path('payments/', include('apps.payments.urls')),
    
    # Notifications URLs
    path('notifications/', include('apps.notifications.urls')),
    
    # Reports URLs
    path('reports/', include('apps.reports.urls')),

#     # Password reset URLs
#     path('password-reset/', 
#          auth_views.PasswordResetView.as_view(template_name="auth/password_reset.html"), 
#          name='password_reset'),

#     path('password-reset/done/', 
#          auth_views.PasswordResetDoneView.as_view(template_name="auth/password_reset_done.html"), 
#          name='password_reset_done'),

#     path('reset/<uidb64>/<token>/', 
#          auth_views.PasswordResetConfirmView.as_view(template_name="auth/password_reset_confirm.html"), 
#          name='password_reset_confirm'),

#     path('reset/done/', 
#          auth_views.PasswordResetCompleteView.as_view(template_name="auth/password_reset_complete.html"), 
#          name='password_reset_complete'),
 ]

# Add this line so /i18n/setlang/ works
urlpatterns += [
    path('i18n/', include('django.conf.urls.i18n')),
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Custom error handlers
handler404 = 'apps.authentication.views.custom_404'
handler500 = 'apps.authentication.views.custom_500'
handler403 = 'apps.authentication.views.custom_403'

# Admin site configuration
admin.site.site_header = "Enterprise Canteen Management"
admin.site.site_title = "Canteen Admin"
admin.site.index_title = "Welcome to Enterprise Canteen Management"