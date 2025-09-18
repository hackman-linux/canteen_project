from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView, ListView
from django.http import JsonResponse
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db.models import Q, Count, Sum, Avg, F
from django.db import models
from django.core.paginator import Paginator
from decimal import Decimal
import json
from django.views.decorators.csrf import csrf_exempt

from .models import MenuItem, MenuCategory, DailyMenu, MenuItemReview, MenuItemFavorite
from apps.orders.models import Order, OrderItem


class EmployeeMenuView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Employee view of available menu items"""
    template_name = 'employee/menu.html'
    
    def test_func(self):
        return self.request.user.is_employee() or self.request.user.is_superuser
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get today's menu if available
        today_menu = DailyMenu.get_today_menu()
        
        if today_menu:
            # Use daily menu
            categories = today_menu.get_categories_with_items()
            context['daily_menu'] = today_menu
        else:
            # Use regular menu
            categories = MenuCategory.objects.filter(
                is_active=True
            ).prefetch_related(
                'menu_items'
            ).annotate(
                items_count=Count('menu_items')
            ).filter(items_count__gt=0)
        
        context['categories'] = categories
        
        # User's favorite items
        user_favorites = MenuItemFavorite.objects.filter(
            user=self.request.user
        ).values_list('menu_item_id', flat=True)
        context['user_favorites'] = list(user_favorites)
        
        # Featured items
        featured_items = MenuItem.objects.filter(
            is_featured=True,
            is_available=True
        )[:6]
        context['featured_items'] = featured_items
        
        # Special offers
        special_items = MenuItem.objects.filter(
            is_special=True,
            is_available=True,
            special_until__gte=timezone.now()
        )[:4]
        context['special_items'] = special_items
        
        return context


@login_required
def employee_menu(request):
    categories = MenuCategory.objects.prefetch_related('menu_items').all()
    menu_categories = []

    for category in categories:
        items = category.menu_items.filter(is_available=True)
        if items.exists():
            menu_categories.append({
                "id": category.id,
                "name": category.name,
                "icon": category.icon or "list",  # fallback icon
                "items": items
            })

    context = {
        "menu_categories": menu_categories,
        "current_date": timezone.now().date(),
    }
    return render(request, "employee/menu.html", context)


@login_required
def menu_view(request):
    """
    Basic menu view for employees/customers to browse items.
    """
    items = MenuItem.objects.filter(is_available=True).select_related('category')
    categories = MenuCategory.objects.filter(is_active=True).prefetch_related('menu_items')

    context = {
        'items': items,
        'categories': categories,
    }
    return render(request, 'employee/menu.html', context)


# Replace your existing menu_management function and MenuManagementView with this:

class MenuManagementView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'menu/menu_management.html'
    
    def test_func(self):
        return self.request.user.is_canteen_admin() or self.request.user.is_superuser
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Filters
        category_filter = self.request.GET.get('category', 'all')
        status_filter = self.request.GET.get('status', 'all')
        search_query = self.request.GET.get('search', '')
        
        # Base queryset
        menu_items = MenuItem.objects.select_related('category').annotate(
            orders_today=Count('order_items__order__created_at__date=timezone.now().date')
        )
        
        # Apply filters
        if category_filter != 'all':
            menu_items = menu_items.filter(category_id=category_filter)
        if status_filter != 'all':
            menu_items = menu_items.filter(is_available=(status_filter == 'available'))
        if search_query:
            menu_items = menu_items.filter(Q(name__icontains=search_query) | Q(description__icontains=search_query))
        
        # Pagination
        paginator = Paginator(menu_items, 20)
        page_number = self.request.GET.get('page')
        context['menu_items'] = paginator.get_page(page_number)
        
        # Stats
        context['total_items'] = MenuItem.objects.count()
        context['available_items'] = MenuItem.objects.filter(is_available=True).count()
        context['total_categories'] = MenuCategory.objects.count()
        context['categories'] = MenuCategory.objects.all()
        
        # Preserve filters in context
        context.update({
            'category_filter': category_filter,
            'status_filter': status_filter,
            'search_query': search_query,
        })
        
        return context
        # Menu statistics
        total_items = menu_items.count()
        available_items = menu_items.filter(is_available=True).count()
        featured_items = menu_items.filter(is_featured=True).count()
        low_stock_items = menu_items.filter(
            current_stock__lte=F('low_stock_threshold')
        ).count()
        
        context.update({
            'menu_items': menu_items,  # Add this line - it was missing!
            'total_items': total_items,
            'available_items': available_items,
            'featured_items': featured_items,
            'low_stock_items': low_stock_items,
        })
        
        # Categories
        categories = MenuCategory.objects.annotate(
            items_count=Count('menu_items')
        ).order_by('display_order')
        context['categories'] = categories
        context['total_categories'] = categories.count()  # Add this for the sidebar
        
        # Recent items
        recent_items = menu_items[:10]
        context['recent_items'] = recent_items
        
        # Top performing items
        today = timezone.now().date()
        top_items = menu_items.filter(
            order_items__order__created_at__date=today,
            order_items__order__status='completed'
        ).annotate(
            revenue_today=Sum(
                F('order_items__quantity') * F('order_items__unit_price')
            )
        ).order_by('-orders_today')[:5]
        context['top_items'] = top_items
        
        return context


def menu_management(request):
    if not (request.user.is_canteen_admin() or request.user.is_superuser):
        messages.error(request, "You do not have permission to access this page.")
        return redirect("dashboard_redirect")

    menu_items = MenuItem.objects.select_related("category").all()
    categories = MenuCategory.objects.all()

    return render(request, "canteen_admin/menu_management.html", {
        "menu_items": menu_items,
        "categories": categories,
    })


@login_required
def add_menu_item(request):
    """Add new menu item with detailed error logging"""
    print(f"Request method: {request.method}")
    print(f"User: {request.user}")
    print(f"Is canteen admin: {request.user.is_canteen_admin()}")
    
    if not request.user.is_canteen_admin():
        print("User is not canteen admin")
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    if request.method == 'POST':
        try:
            print(f"POST data: {request.POST}")
            print(f"FILES: {request.FILES}")
            
            # Basic validation
            required_fields = ['name', 'price', 'category']
            for field in required_fields:
                if not request.POST.get(field):
                    return JsonResponse({'error': f'{field} is required'}, status=400)
            
            # Get category
            category_id = request.POST.get('category')
            print(f"Category ID: {category_id}")
            
            try:
                category = MenuCategory.objects.get(id=category_id)
                print(f"Found category: {category.name}")
            except MenuCategory.DoesNotExist:
                return JsonResponse({'error': 'Invalid category selected'}, status=400)
            
            # Create menu item
            menu_item_data = {
                'category': category,
                'name': request.POST['name'],
                'description': request.POST.get('description', ''),
                'price': Decimal(str(request.POST['price'])),
                'preparation_time': int(request.POST.get('prep_time', 15)),
                'current_stock': int(request.POST.get('current_stock', 100)),
                'spice_level': request.POST.get('spice_level', 'none'),
                'is_available': 'is_available' in request.POST,
                'created_by': request.user
            }
            
            print(f"Creating menu item with data: {menu_item_data}")
            
            menu_item = MenuItem.objects.create(**menu_item_data)
            
            # Handle image upload
            if 'image' in request.FILES:
                menu_item.image = request.FILES['image']
                menu_item.save()
                print("Image uploaded successfully")
            
            # Handle dietary tags
            dietary_tags = []
            if request.POST.get('is_vegetarian'):
                dietary_tags.append('vegetarian')
            if request.POST.get('is_spicy'):
                dietary_tags.append('spicy')
            
            if dietary_tags:
                menu_item.dietary_tags = dietary_tags
                menu_item.save()
                print(f"Dietary tags set: {dietary_tags}")
            
            print(f"Menu item created successfully: {menu_item.id}")
            
            return JsonResponse({
                'success': True,
                'message': 'Menu item added successfully',
                'item_id': str(menu_item.id),
                'item_name': menu_item.name
            })
            
        except Exception as e:
            print(f"Error creating menu item: {str(e)}")
            import traceback
            traceback.print_exc()
            return JsonResponse({'error': f'Error adding menu item: {str(e)}'}, status=400)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def toggle_favorite(request, item_id):
    """Toggle favorite status for a menu item"""
    if not request.user.is_employee():
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    if request.method == 'POST':
        menu_item = get_object_or_404(MenuItem, id=item_id)
        
        favorite, created = MenuItemFavorite.objects.get_or_create(
            user=request.user,
            menu_item=menu_item
        )
        
        if not created:
            # Remove from favorites
            favorite.delete()
            is_favorite = False
        else:
            # Added to favorites
            is_favorite = True
        
        return JsonResponse({
            'is_favorite': is_favorite,
            'message': 'Added to favorites' if is_favorite else 'Removed from favorites'
        })
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def menu_item_details(request, item_id):
    """Get detailed information about a menu item"""
    menu_item = get_object_or_404(MenuItem, id=item_id)
    
    # Check if user has favorited this item
    is_favorite = False
    if request.user.is_authenticated:
        is_favorite = MenuItemFavorite.objects.filter(
            user=request.user,
            menu_item=menu_item
        ).exists()
    
    # Get reviews
    reviews = MenuItemReview.objects.filter(
        menu_item=menu_item
    ).select_related('user').order_by('-created_at')[:5]
    
    # Check if user has ordered this item before
    has_ordered = False
    if request.user.is_authenticated and request.user.is_employee():
        has_ordered = OrderItem.objects.filter(
            order__customer=request.user,
            menu_item=menu_item,
            order__status='completed'
        ).exists()
    
    data = {
        'id': str(menu_item.id),
        'name': menu_item.name,
        'description': menu_item.description,
        'price': str(menu_item.price),
        'display_price': str(menu_item.get_display_price()),
        'category': menu_item.category.name,
        'is_available': menu_item.is_available,
        'is_in_stock': menu_item.is_in_stock(),
        'is_special': menu_item.is_special_active(),
        'discount_percentage': menu_item.get_discount_percentage(),
        'preparation_time': menu_item.preparation_time,
        'spice_level': menu_item.get_spice_level_display(),
        'dietary_tags': menu_item.get_dietary_tags_display(),
        'calories': menu_item.calories,
        'average_rating': str(menu_item.average_rating),
        'total_reviews': menu_item.total_reviews,
        'rating_stars': menu_item.get_rating_stars(),
        'is_favorite': is_favorite,
        'has_ordered': has_ordered,
        'allergens': menu_item.allergens,
        'reviews': [{
            'user': review.user.get_short_name(),
            'rating': review.rating,
            'comment': review.comment,
            'date': review.created_at.strftime('%b %d, %Y')
        } for review in reviews]
    }
    
    return JsonResponse(data)


@login_required
def inventory_management(request):
    """Inventory management for canteen admins"""
    if not request.user.is_canteen_admin():
        return redirect('dashboard_redirect')
    
    # Get all menu items with stock information
    items = MenuItem.objects.select_related('category').annotate(
        orders_today=Count(
            'order_items',
            filter=Q(
                order_items__order__created_at__date=timezone.now().date(),
                order_items__order__status='completed'
            )
        )
    ).order_by('current_stock')
    
    # Filter by stock status
    stock_filter = request.GET.get('stock_filter', 'all')
    if stock_filter == 'low':
        items = items.filter(current_stock__lte=F('low_stock_threshold'))
    elif stock_filter == 'out':
        items = items.filter(current_stock=0)
    elif stock_filter == 'available':
        items = items.filter(current_stock__gt=0)
    
    # Pagination
    paginator = Paginator(items, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'stock_filter': stock_filter,
        'low_stock_count': MenuItem.objects.filter(
            current_stock__lte=F('low_stock_threshold')
        ).count(),
        'out_of_stock_count': MenuItem.objects.filter(current_stock=0).count(),
    }
    
    return render(request, 'canteen_admin/inventory.html', context)

def update_status(request, item_id):
    """Canteen Admin - Update availability status of a menu item"""
    item = get_object_or_404(MenuItem, id=item_id)

    # Toggle between available/unavailable
    if item.is_available:
        item.is_available = False
        messages.info(request, f"{item.name} marked as unavailable.")
    else:
        item.is_available = True
        messages.success(request, f"{item.name} marked as available.")

    item.save()
    return redirect("menu:menu_management")


@login_required
def update_stock(request, item_id):
    """Update stock for a menu item"""
    if not request.user.is_canteen_admin():
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    if request.method == 'POST':
        menu_item = get_object_or_404(MenuItem, id=item_id)
        
        try:
            data = json.loads(request.body)
            action = data.get('action')
            quantity = int(data.get('quantity', 0))
            
            if action == 'add':
                menu_item.restock(quantity)
                message = f'Added {quantity} units to {menu_item.name}'
            elif action == 'set':
                menu_item.current_stock = quantity
                menu_item.save()
                message = f'Stock set to {quantity} for {menu_item.name}'
            else:
                return JsonResponse({'error': 'Invalid action'}, status=400)
            
            return JsonResponse({
                'success': True,
                'message': message,
                'new_stock': menu_item.current_stock,
                'is_low_stock': menu_item.is_low_stock()
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def menu_categories_api(request):
    """API endpoint for menu categories"""
    categories = MenuCategory.objects.filter(is_active=True).annotate(
        items_count=Count('menu_items', filter=Q(menu_items__is_available=True))
    ).order_by('display_order')
    
    data = [{
        'id': str(category.id),
        'name': category.name,
        'description': category.description,
        'icon': category.icon,
        'color': category.color,
        'items_count': category.items_count
    } for category in categories]
    
    return JsonResponse({'categories': data})


@login_required
def daily_menu_api(request):
    """API endpoint for today's daily menu"""
    today_menu = DailyMenu.get_today_menu()
    
    if not today_menu:
        return JsonResponse({'error': 'No menu available for today'}, status=404)
    
    categories_data = []
    for category in today_menu.get_categories_with_items():
        items_data = []
        for item in category.menu_items.all():
            daily_item = item.daily_menu_items.filter(daily_menu=today_menu).first()
            items_data.append({
                'id': str(item.id),
                'name': item.name,
                'description': item.description,
                'price': str(daily_item.get_effective_price() if daily_item else item.get_display_price()),
                'is_available': item.is_available and item.is_in_stock(),
                'is_featured_today': daily_item.is_featured_today if daily_item else False,
                'preparation_time': item.preparation_time,
            })
        
        categories_data.append({
            'id': str(category.id),
            'name': category.name,
            'items': items_data
        })
    
    return JsonResponse({
        'menu': {
            'date': today_menu.date.isoformat(),
            'special_message': today_menu.special_message,
            'categories': categories_data
        }
    })


@login_required
def create_menu_category(request):
    """Create a new menu category"""
    if not request.user.is_canteen_admin():
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            category = MenuCategory.objects.create(
                name=data['name'],
                description=data.get('description', ''),
                icon=data.get('icon', 'utensils'),
                color=data.get('color', '#007bff'),
                display_order=data.get('display_order', 0),
                is_active=data.get('is_active', True)
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Category created successfully',
                'category_id': str(category.id),
                'category_name': category.name
            })
            
        except Exception as e:
            return JsonResponse({
                'error': f'Error creating category: {str(e)}'
            }, status=400)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def update_menu_item(request, item_id):
    """Update an existing menu item"""
    if not request.user.is_canteen_admin():
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    if request.method == 'POST':
        try:
            menu_item = get_object_or_404(MenuItem, id=item_id)
            data = json.loads(request.body)
            
            # Update fields
            menu_item.name = data.get('name', menu_item.name)
            menu_item.description = data.get('description', menu_item.description)
            menu_item.price = Decimal(data.get('price', menu_item.price))
            menu_item.preparation_time = int(data.get('preparation_time', menu_item.preparation_time))
            menu_item.spice_level = data.get('spice_level', menu_item.spice_level)
            menu_item.is_available = data.get('is_available', menu_item.is_available)
            menu_item.is_featured = data.get('is_featured', menu_item.is_featured)
            
            # Update dietary tags if provided
            if 'dietary_tags' in data:
                menu_item.dietary_tags = data['dietary_tags']
            
            menu_item.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Menu item updated successfully',
                'item_name': menu_item.name
            })
            
        except Exception as e:
            return JsonResponse({
                'error': f'Error updating menu item: {str(e)}'
            }, status=400)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def delete_menu_item(request, item_id):
    """Delete a menu item"""
    if not request.user.is_canteen_admin():
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    if request.method == 'DELETE':
        try:
            menu_item = get_object_or_404(MenuItem, id=item_id)
            item_name = menu_item.name
            
            # Check if item has been ordered
            has_orders = OrderItem.objects.filter(menu_item=menu_item).exists()
            
            if has_orders:
                # Don't delete, just deactivate
                menu_item.is_available = False
                menu_item.save()
                message = f'Menu item "{item_name}" has been deactivated'
            else:
                # Safe to delete
                menu_item.delete()
                message = f'Menu item "{item_name}" has been deleted'
            
            return JsonResponse({
                'success': True,
                'message': message
            })
            
        except Exception as e:
            return JsonResponse({
                'error': f'Error deleting menu item: {str(e)}'
            }, status=400)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def menu_item_reviews(request, item_id):
    """Get reviews for a menu item"""
    menu_item = get_object_or_404(MenuItem, id=item_id)
    
    reviews = MenuItemReview.objects.filter(
        menu_item=menu_item
    ).select_related('user').order_by('-created_at')
    
    # Pagination
    paginator = Paginator(reviews, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    reviews_data = []
    for review in page_obj:
        reviews_data.append({
            'id': str(review.id),
            'user': review.user.get_short_name(),
            'rating': review.rating,
            'comment': review.comment,
            'date': review.created_at.strftime('%b %d, %Y at %I:%M %p'),
            'helpful_count': review.helpful_count
        })
    
    return JsonResponse({
        'reviews': reviews_data,
        'has_previous': page_obj.has_previous(),
        'has_next': page_obj.has_next(),
        'current_page': page_obj.number,
        'total_pages': page_obj.paginator.num_pages,
        'total_reviews': reviews.count()
    })


@login_required
def add_menu_review(request, item_id):
    """Add a review for a menu item"""
    if not request.user.is_employee():
        return JsonResponse({'error': 'Only employees can add reviews'}, status=403)
    
    if request.method == 'POST':
        try:
            menu_item = get_object_or_404(MenuItem, id=item_id)
            data = json.loads(request.body)
            
            # Check if user has ordered this item
            has_ordered = OrderItem.objects.filter(
                order__customer=request.user,
                menu_item=menu_item,
                order__status='completed'
            ).exists()
            
            if not has_ordered:
                return JsonResponse({
                    'error': 'You can only review items you have ordered'
                }, status=400)
            
            # Check if user already reviewed this item
            existing_review = MenuItemReview.objects.filter(
                user=request.user,
                menu_item=menu_item
            ).first()
            
            if existing_review:
                # Update existing review
                existing_review.rating = int(data['rating'])
                existing_review.comment = data.get('comment', '')
                existing_review.save()
                message = 'Review updated successfully'
            else:
                # Create new review
                MenuItemReview.objects.create(
                    user=request.user,
                    menu_item=menu_item,
                    rating=int(data['rating']),
                    comment=data.get('comment', '')
                )
                message = 'Review added successfully'
            
            # Update menu item rating
            menu_item.update_rating()
            
            return JsonResponse({
                'success': True,
                'message': message,
                'new_average_rating': str(menu_item.average_rating),
                'total_reviews': menu_item.total_reviews
            })
            
        except Exception as e:
            return JsonResponse({
                'error': f'Error adding review: {str(e)}'
            }, status=400)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def search_menu_items(request):
    """Search menu items"""
    query = request.GET.get('q', '').strip()
    category_id = request.GET.get('category')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    dietary_tags = request.GET.getlist('dietary_tags')
    spice_level = request.GET.get('spice_level')
    
    items = MenuItem.objects.filter(is_available=True).select_related('category')
    
    # Text search
    if query:
        items = items.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(category__name__icontains=query)
        )
    
    # Category filter
    if category_id:
        items = items.filter(category_id=category_id)
    
    # Price range filter
    if min_price:
        items = items.filter(price__gte=Decimal(min_price))
    if max_price:
        items = items.filter(price__lte=Decimal(max_price))
    
    # Dietary tags filter
    if dietary_tags:
        for tag in dietary_tags:
            items = items.filter(dietary_tags__icontains=tag)
    
    # Spice level filter
    if spice_level:
        items = items.filter(spice_level=spice_level)
    
    # Order by relevance and popularity
    items = items.annotate(
        order_count=Count('order_items')
    ).order_by('-order_count', 'name')
    
    # Pagination
    paginator = Paginator(items, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get user favorites
    user_favorites = []
    if request.user.is_authenticated:
        user_favorites = list(MenuItemFavorite.objects.filter(
            user=request.user,
            menu_item__in=page_obj
        ).values_list('menu_item_id', flat=True))
    
    items_data = []
    for item in page_obj:
        items_data.append({
            'id': str(item.id),
            'name': item.name,
            'description': item.description[:100] + '...' if len(item.description) > 100 else item.description,
            'price': str(item.get_display_price()),
            'category': item.category.name,
            'is_in_stock': item.is_in_stock(),
            'is_special': item.is_special_active(),
            'preparation_time': item.preparation_time,
            'average_rating': str(item.average_rating),
            'total_reviews': item.total_reviews,
            'is_favorite': str(item.id) in user_favorites
        })
    
    return JsonResponse({
        'items': items_data,
        'has_previous': page_obj.has_previous(),
        'has_next': page_obj.has_next(),
        'current_page': page_obj.number,
        'total_pages': page_obj.paginator.num_pages,
        'total_items': items.count()
    })

class MenuStatisticsView(TemplateView):
    template_name = "menu/statistics.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Menu statistics
        total_items = MenuItem.objects.count()
        available_items = MenuItem.objects.filter(is_available=True).count()
        featured_items = MenuItem.objects.filter(is_featured=True).count()
        low_stock_items = MenuItem.objects.filter(
            current_stock__lte=F('low_stock_threshold')
        ).count()

        context.update({
            'total_items': total_items,
            'available_items': available_items,
            'featured_items': featured_items,
            'low_stock_items': low_stock_items,
        })

        # Categories
        categories = MenuCategory.objects.annotate(
            items_count=Count('menu_items')
        ).order_by('display_order')
        context['categories'] = categories

        # Recent items
        recent_items = MenuItem.objects.select_related('category').order_by('-created_at')[:10]
        context['recent_items'] = recent_items

        # Top performing items
        today = timezone.now().date()
        top_items = MenuItem.objects.filter(
            order_items__order__created_at__date=today,
            order_items__order__status='completed'
        ).annotate(
            orders_today=Count('order_items'),
            revenue_today=Sum(
                F('order_items__quantity') * F('order_items__unit_price')
            )
        ).order_by('-orders_today')[:5]
        context['top_items'] = top_items

        return context

@require_POST
def bulk_make_available(request):
    """Mark selected menu items as available"""
    item_ids = request.POST.getlist("items")
    if item_ids:
        MenuItem.objects.filter(id__in=item_ids).update(is_available=True)
        messages.success(request, f"{len(item_ids)} items marked as available.")
    return redirect("menu:menu_management")


@require_POST
def bulk_make_unavailable(request):
    """Mark selected menu items as unavailable"""
    item_ids = request.POST.getlist("items")
    if item_ids:
        MenuItem.objects.filter(id__in=item_ids).update(is_available=False)
        messages.success(request, f"{len(item_ids)} items marked as unavailable.")
    return redirect("menu:menu_management")


@require_POST
def bulk_change_category(request):
    """Change category for multiple items"""
    item_ids = request.POST.getlist("items")
    new_category_id = request.POST.get("category_id")
    if item_ids and new_category_id:
        MenuItem.objects.filter(id__in=item_ids).update(category_id=new_category_id)
        messages.success(request, f"Category changed for {len(item_ids)} items.")
    return redirect("menu:menu_management")

@require_POST
def bulk_delete(request):
    """Bulk delete selected menu items"""
    item_ids = request.POST.getlist("item_ids[]")  # JS sends as array

    if not item_ids:
        return JsonResponse({"success": False, "message": "No items selected."}, status=400)

    deleted_count, _ = MenuItem.objects.filter(id__in=item_ids).delete()

    return JsonResponse({"success": True, "deleted_count": deleted_count})

# Add these functions to your views.py file

@login_required
def toggle_item_availability(request, item_id):
    """Toggle availability status of a menu item via AJAX"""
    if not request.user.is_canteen_admin():
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    if request.method == 'POST':
        try:
            menu_item = get_object_or_404(MenuItem, id=item_id)
            
            # Toggle availability
            menu_item.is_available = not menu_item.is_available
            menu_item.save()
            
            status_text = "available" if menu_item.is_available else "unavailable"
            message = f"{menu_item.name} marked as {status_text}."
            
            return JsonResponse({
                'success': True,
                'message': message,
                'is_available': menu_item.is_available
            })
            
        except Exception as e:
            return JsonResponse({
                'error': f'Error updating availability: {str(e)}'
            }, status=400)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required 
def update_status(request, item_id):
    """Update availability status of a menu item (for form submissions)"""
    if not request.user.is_canteen_admin():
        messages.error(request, 'Unauthorized access.')
        return redirect('dashboard_redirect')
    
    item = get_object_or_404(MenuItem, id=item_id)

    # Toggle between available/unavailable
    if item.is_available:
        item.is_available = False
        messages.info(request, f"{item.name} marked as unavailable.")
    else:
        item.is_available = True
        messages.success(request, f"{item.name} marked as available.")

    item.save()
    return redirect("menu:menu_management")


# Fix the add_menu_item function to handle form data correctly
@login_required
def add_menu_item(request):
    """Add new menu item via AJAX or form submission"""
    if not request.user.is_canteen_admin():
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    if request.method == 'POST':
        try:
            # Handle both JSON and form data
            if request.content_type == 'application/json':
                data = json.loads(request.body)
                category_id = data['category_id']
            else:
                # Handle form data
                data = request.POST
                category_id = data.get('category')
            
            # Get category
            category = get_object_or_404(MenuCategory, id=category_id)
            
            # Create menu item
            menu_item = MenuItem.objects.create(
                category=category,
                name=data['name'],
                description=data.get('description', ''),
                price=Decimal(str(data['price'])),
                preparation_time=int(data.get('prep_time', data.get('preparation_time', 15))),
                current_stock=int(data.get('current_stock', 100)),
                spice_level=data.get('spice_level', 'none'),
                is_available=data.get('is_available', 'on') == 'on' if 'is_available' in data else True,
                created_by=request.user
            )
            
            # Handle image upload for form data
            if 'image' in request.FILES:
                menu_item.image = request.FILES['image']
                menu_item.save()
            
            # Handle dietary tags
            dietary_tags = []
            if data.get('is_vegetarian'):
                dietary_tags.append('vegetarian')
            if data.get('is_spicy'):
                dietary_tags.append('spicy')
            
            if dietary_tags:
                menu_item.dietary_tags = dietary_tags
                menu_item.save()
            
            if request.content_type == 'application/json':
                return JsonResponse({
                    'success': True,
                    'message': 'Menu item added successfully',
                    'item_id': str(menu_item.id),
                    'item_name': menu_item.name
                })
            else:
                messages.success(request, f'Menu item "{menu_item.name}" added successfully')
                return redirect('menu:menu_management')
            
        except Exception as e:
            error_msg = f'Error adding menu item: {str(e)}'
            if request.content_type == 'application/json':
                return JsonResponse({'error': error_msg}, status=400)
            else:
                messages.error(request, error_msg)
                return redirect('menu:menu_management')
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def create_menu_category(request):
    """Create a new menu category - fixed version"""
    if not request.user.is_canteen_admin():
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    if request.method == 'POST':
        try:
            # Handle both JSON and form data
            if request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                data = request.POST
            
            category = MenuCategory.objects.create(
                name=data['name'],
                description=data.get('description', ''),
                icon=data.get('icon', 'utensils'),
                color=data.get('color', '#007bff'),
                display_order=int(data.get('order', data.get('display_order', 0))),
                is_active=data.get('is_active', True)
            )
            
            if request.content_type == 'application/json':
                return JsonResponse({
                    'success': True,
                    'message': 'Category created successfully',
                    'category_id': str(category.id),
                    'category_name': category.name
                })
            else:
                messages.success(request, f'Category "{category.name}" created successfully')
                return redirect('menu:menu_management')
            
        except Exception as e:
            error_msg = f'Error creating category: {str(e)}'
            if request.content_type == 'application/json':
                return JsonResponse({'error': error_msg}, status=400)
            else:
                messages.error(request, error_msg)
                return redirect('menu:menu_management')
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@login_required
def test_menu_management(request):
    """Test view to debug menu management issues"""
    
    context = {
        'user': request.user,
        'is_canteen_admin': request.user.is_canteen_admin() if hasattr(request.user, 'is_canteen_admin') else False,
        'categories': MenuCategory.objects.all(),
        'menu_items_count': MenuItem.objects.count(),
    }
    
    return JsonResponse({
        'success': True,
        'data': {
            'user_id': request.user.id,
            'user_role': getattr(request.user, 'role', 'unknown'),
            'is_canteen_admin': context['is_canteen_admin'],
            'categories_count': context['categories'].count(),
            'menu_items_count': context['menu_items_count'],
        }
    })
 # Remove this after debugging
@login_required
def debug_add_item(request):
    """Debug version without CSRF for testing"""
    if request.method == 'POST':
        print("POST data received:")
        for key, value in request.POST.items():
            print(f"  {key}: {value}")
        
        return JsonResponse({
            'success': True,
            'message': 'Data received successfully',
            'data': dict(request.POST.items())
        })
    
    return JsonResponse({'error': 'Only POST allowed'}, status=405)