from django.urls import path
from . import views

app_name = "menu" 

urlpatterns = [
    # Employee views
    path('employee/', views.employee_menu, name='employee_menu'),
    path('', views.menu_view, name='view'),

    # Admin views
    path('management/', views.menu_management, name='menu_management'),
    path('inventory/', views.inventory_management, name='inventory_management'),

    # Menu item CRUD
    path('item/add/', views.add_menu_item, name='add_menu_item'),
    path('item/<uuid:item_id>/', views.menu_item_details, name='menu_item_details'),
    path('item/<uuid:item_id>/update/', views.update_menu_item, name='update_menu_item'),
    path('item/<uuid:item_id>/delete/', views.delete_menu_item, name='delete_menu_item'),

    # Stock management
    path('item/<uuid:item_id>/stock/', views.update_stock, name='update_stock'),

    # Favorites
    path('item/<uuid:item_id>/favorite/', views.toggle_favorite, name='toggle_favorite'),

    # Reviews
    path('item/<uuid:item_id>/reviews/', views.menu_item_reviews, name='menu_item_reviews'),
    path('item/<uuid:item_id>/reviews/add/', views.add_menu_review, name='add_menu_review'),

    # # APIs
    # path('api/categories/', views.menu_categories_api, name='menu_categories_api'),
    # path('api/daily/', views.daily_menu_api, name='daily_menu_api'),
    # path('api/search/', views.search_menu_items, name='search_menu_items'),

    # Category CRUD
    path('category/create/', views.create_menu_category, name='create_menu_category'),
]
