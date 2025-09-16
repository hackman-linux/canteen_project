# urls.py for menu app (updated to include employee menu)
from django.urls import path
from . import views

app_name = 'menu'

urlpatterns = [
    # Employee Views
    path('', views.employee_menu, name='employee_menu'),
    path('view/', views.menu_view, name='view'),  # Alternative endpoint
    
    # Menu Item Details
    path('item/<uuid:item_id>/', views.menu_item_details, name='item_detail'),
    path('item/<uuid:item_id>/toggle-favorite/', views.toggle_favorite, name='toggle_favorite'),
    path('item/<uuid:item_id>/reviews/', views.menu_item_reviews, name='item_reviews'),
    path('item/<uuid:item_id>/add-review/', views.add_menu_review, name='add_review'),
    
    # Search and Filtering
    path('search/', views.search_menu_items, name='search'),
    path('categories/api/', views.menu_categories_api, name='categories_api'),
    path('daily-menu/api/', views.daily_menu_api, name='daily_menu_api'),
    
    # Admin Views
    path('management/', views.MenuManagementView.as_view(), name='menu_management'),
    path('inventory/', views.inventory_management, name='inventory'),
    path('statistics/', views.MenuStatisticsView.as_view(), name='statistics'),
    
    # Admin Actions
    path('add-item/', views.add_menu_item, name='add_item'),
    path('item/<uuid:item_id>/update/', views.update_menu_item, name='update_item'),
    path('item/<uuid:item_id>/delete/', views.delete_menu_item, name='delete_item'),
    path('item/<uuid:item_id>/toggle-availability/', views.toggle_item_availability, name='toggle_availability'),
    path('item/<uuid:item_id>/update-status/', views.update_status, name='update_status'),
    path('item/<uuid:item_id>/update-stock/', views.update_stock, name='update_stock'),
    
    # Category Management
    path('categories/create/', views.create_menu_category, name='create_category'),
    
    # Bulk Operations
    path('bulk/make-available/', views.bulk_make_available, name='bulk_make_available'),
    path('bulk/make-unavailable/', views.bulk_make_unavailable, name='bulk_make_unavailable'),
    path('bulk/change-category/', views.bulk_change_category, name='bulk_change_category'),
    path('bulk/delete/', views.bulk_delete, name='bulk_delete'),
]