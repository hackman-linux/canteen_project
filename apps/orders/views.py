
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView, ListView
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Count, Sum, Avg, F
from django.core.paginator import Paginator
from django.db import transaction
from decimal import Decimal
import json

from .models import Order, OrderItem, OrderQueue, ReorderItem
from apps.menu.models import MenuItem
from apps.payments.models import Payment, WalletTransaction
from apps.notifications.models import Notification


@login_required
def place_order(request):
    """Place a new order - Employee only"""
    if not request.user.is_employee():
        return redirect('dashboard_redirect')
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            cart_items = data.get('items', [])
            delivery_time = data.get('delivery_time')
            delivery_date = data.get('delivery_date')
            special_instructions = data.get('special_instructions', '')
            
            if not cart_items:
                return JsonResponse({'error': 'Cart is empty'}, status=400)
            
            with transaction.atomic():
                # Create order
                order = Order.objects.create(
                    customer=request.user,
                    delivery_time=delivery_time,
                    delivery_date=delivery_date,
                    special_instructions=special_instructions,
                )
                
                total_amount = Decimal('0.00')
                
                # Create order items
                for cart_item in cart_items:
                    menu_item = get_object_or_404(MenuItem, id=cart_item['item_id'])
                    quantity = int(cart_item['quantity'])
                    
                    # Check availability and stock
                    if not menu_item.is_available or not menu_item.is_in_stock():
                        return JsonResponse({
                            'error': f'{menu_item.name} is not available'
                        }, status=400)
                    
                    # Check stock quantity
                    if menu_item.current_stock < quantity:
                        return JsonResponse({
                            'error': f'Only {menu_item.current_stock} units of {menu_item.name} available'
                        }, status=400)
                    
                    # Create order item
                    order_item = OrderItem.objects.create(
                        order=order,
                        menu_item=menu_item,
                        quantity=quantity,
                        unit_price=menu_item.get_display_price(),
                        special_instructions=cart_item.get('special_instructions', ''),
                        customizations=cart_item.get('customizations', {})
                    )
                    
                    total_amount += order_item.total_price
                    
                    # Update stock
                    menu_item.update_stock(quantity)
                    menu_item.increment_orders(quantity)
                    
                    # Update reorder items
                    reorder_item, created = ReorderItem.objects.get_or_create(
                        user=request.user,
                        menu_item=menu_item,
                        defaults={'quantity': quantity}
                    )
                    if not created:
                        reorder_item.increment_order_count()
                
                # Update order totals
                order.calculate_totals()
                
                # Add to order queue
                queue_item = OrderQueue.objects.create(
                    order=order,
                    queue_position=OrderQueue.objects.count() + 1
                )
                
                # Create notification for canteen admins
                Notification.objects.create(
                    title='New Order Received',
                    message=f'New order #{order.order_number} from {request.user.get_short_name()}',
                    notification_type='order_status',
                    target_audience='canteen_admins',
                    order=order
                )
                
                return JsonResponse({
                    'success': True,
                    'message': 'Order placed successfully',
                    'order_id': str(order.id),
                    'order_number': order.order_number,
                    'total_amount': str(order.total_amount)
                })
                
        except Exception as e:
            return JsonResponse({'error': f'Error placing order: {str(e)}'}, status=400)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def add_to_cart(request):
    """Add item to cart (session-based cart)"""
    if not request.user.is_employee():
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            menu_item = get_object_or_404(MenuItem, id=data['item_id'])
            quantity = int(data.get('quantity', 1))
            
            # Check availability
            if not menu_item.is_available or not menu_item.is_in_stock():
                return JsonResponse({'error': 'Item is not available'}, status=400)
            
            # Get or create cart in session
            cart = request.session.get('cart', {})
            item_id = str(menu_item.id)
            
            if item_id in cart:
                cart[item_id]['quantity'] += quantity
            else:
                cart[item_id] = {
                    'name': menu_item.name,
                    'price': str(menu_item.get_display_price()),
                    'quantity': quantity,
                    'image': menu_item.image.url if menu_item.image else None
                }
            
            request.session['cart'] = cart
            
            # Calculate cart totals
            cart_total = sum(
                Decimal(item['price']) * item['quantity'] 
                for item in cart.values()
            )
            cart_count = sum(item['quantity'] for item in cart.values())
            
            return JsonResponse({
                'success': True,
                'message': f'{menu_item.name} added to cart',
                'cart_count': cart_count,
                'cart_total': str(cart_total)
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def quick_order(request):
    """Quick reorder from previous orders"""
    if not request.user.is_employee():
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            reorder_items = data.get('items', [])
            
            if not reorder_items:
                return JsonResponse({'error': 'No items selected'}, status=400)
            
            with transaction.atomic():
                # Create order
                order = Order.objects.create(
                    customer=request.user,
                    delivery_time=data.get('delivery_time', '12:00'),
                    special_instructions='Quick reorder'
                )
                
                # Add items to order
                for item_data in reorder_items:
                    reorder_item = get_object_or_404(
                        ReorderItem, 
                        id=item_data['reorder_id'],
                        user=request.user
                    )
                    
                    menu_item = reorder_item.menu_item
                    quantity = item_data.get('quantity', reorder_item.quantity)
                    
                    # Check availability
                    if not menu_item.is_available or not menu_item.is_in_stock():
                        continue  # Skip unavailable items
                    
                    OrderItem.objects.create(
                        order=order,
                        menu_item=menu_item,
                        quantity=quantity,
                        unit_price=menu_item.get_display_price()
                    )
                    
                    # Update stock and reorder count
                    menu_item.update_stock(quantity)
                    reorder_item.increment_order_count()
                
                # Calculate totals
                order.calculate_totals()
                
                if order.items.count() == 0:
                    order.delete()
                    return JsonResponse({'error': 'No items were available'}, status=400)
                
                return JsonResponse({
                    'success': True,
                    'message': 'Quick order placed successfully',
                    'order_number': order.order_number
                })
                
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def order_history(request):
    """Employee order history"""
    if not request.user.is_employee():
        return redirect('dashboard_redirect')
    
    orders = Order.objects.filter(
        customer=request.user
    ).select_related('customer').prefetch_related('items__menu_item').order_by('-created_at')
    
    # Filter by status if provided
    status_filter = request.GET.get('status')
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    # Filter by date range
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from:
        orders = orders.filter(created_at__date__gte=date_from)
    if date_to:
        orders = orders.filter(created_at__date__lte=date_to)
    
    # Pagination
    paginator = Paginator(orders, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Order statistics
    stats = orders.aggregate(
        total_orders=Count('id'),
        total_spent=Sum('total_amount'),
        avg_order_value=Avg('total_amount')
    )
    
    context = {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'date_from': date_from,
        'date_to': date_to,
        'stats': stats,
        'order_statuses': Order.STATUS_CHOICES
    }
    
    return render(request, 'orders/history.html', context)


@login_required
def cancel_order(request, order_id):
    """Cancel an order"""
    if request.method == 'POST':
        order = get_object_or_404(Order, id=order_id, customer=request.user)
        
        if not order.can_be_cancelled():
            return JsonResponse({'error': 'Order cannot be cancelled'}, status=400)
        
        with transaction.atomic():
            # Restore stock
            for item in order.items.all():
                item.menu_item.restock(item.quantity)
            
            # Update order status
            order.update_status('cancelled', request.user)
            
            # Process refund if payment was made
            if order.payments.filter(status='completed').exists():
                # Add refund to wallet
                request.user.add_to_wallet(order.total_amount)
                
                # Create wallet transaction
                WalletTransaction.objects.create(
                    user=request.user,
                    transaction_type='credit',
                    source='refund',
                    amount=order.total_amount,
                    balance_before=request.user.wallet_balance - order.total_amount,
                    balance_after=request.user.wallet_balance,
                    description=f'Refund for cancelled order #{order.order_number}',
                    reference=order.order_number
                )
        
        return JsonResponse({
            'success': True,
            'message': 'Order cancelled successfully'
        })
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


# Canteen Admin Views
@login_required
def orders_management(request):
    """Canteen admin orders management"""
    if not request.user.is_canteen_admin():
        return redirect('dashboard_redirect')
    
    orders = Order.objects.select_related('customer').prefetch_related('items__menu_item')
    
    # Filter by status
    status_filter = request.GET.get('status', 'all')
    if status_filter != 'all':
        orders = orders.filter(status=status_filter)
    
    # Filter by date
    date_filter = request.GET.get('date', 'today')
    if date_filter == 'today':
        orders = orders.filter(created_at__date=timezone.now().date())
    elif date_filter == 'week':
        week_ago = timezone.now().date() - timezone.timedelta(days=7)
        orders = orders.filter(created_at__date__gte=week_ago)
    
    orders = orders.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(orders, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Statistics
    stats = orders.aggregate(
        total_orders=Count('id'),
        total_revenue=Sum('total_amount', filter=Q(status='completed')),
        pending_orders=Count('id', filter=Q(status__in=['pending', 'confirmed', 'preparing'])),
        completed_orders=Count('id', filter=Q(status='completed'))
    )
    
    context = {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'date_filter': date_filter,
        'stats': stats,
        'order_statuses': Order.STATUS_CHOICES
    }
    
    return render(request, 'orders/management.html', context)


@login_required
def order_queue(request):
    """Order queue management for canteen admins"""
    if not request.user.is_canteen_admin():
        return redirect('dashboard_redirect')
    
    # Get orders in queue (confirmed and preparing)
    queue_items = OrderQueue.objects.filter(
        order__status__in=['confirmed', 'preparing']
    ).select_related('order__customer').order_by('priority', 'queue_position', 'created_at')
    
    context = {
        'queue_items': queue_items,
        'total_in_queue': queue_items.count()
    }
    
    return render(request, 'orders/queue.html', context)


@login_required
def update_order_status(request):
    """Update order status - Canteen Admin only"""
    if not request.user.is_canteen_admin():
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            order = get_object_or_404(Order, id=data['order_id'])
            new_status = data['status']
            
            # Validate status transition
            valid_transitions = {
                'pending': ['confirmed', 'cancelled'],
                'confirmed': ['preparing', 'cancelled'],
                'preparing': ['ready', 'cancelled'],
                'ready': ['completed'],
                'completed': [],
                'cancelled': []
            }
            
            if new_status not in valid_transitions.get(order.status, []):
                return JsonResponse({
                    'error': f'Cannot change status from {order.status} to {new_status}'
                }, status=400)
            
            # Update order status
            order.update_status(new_status, request.user)
            
            return JsonResponse({
                'success': True,
                'message': f'Order status updated to {new_status}',
                'new_status': new_status,
                'status_display': order.get_status_display()
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def order_details_api(request, order_id):
    """Get order details via API"""
    order = get_object_or_404(Order, id=order_id)
    
    # Check permissions
    if not (request.user == order.customer or request.user.is_canteen_admin() or request.user.is_system_admin()):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    items_data = []
    for item in order.items.all():
        items_data.append({
            'name': item.menu_item.name,
            'quantity': item.quantity,
            'unit_price': str(item.unit_price),
            'total_price': str(item.total_price),
            'special_instructions': item.special_instructions,
            'customizations': item.get_customizations_display()
        })
    
    data = {
        'id': str(order.id),
        'order_number': order.order_number,
        'customer': order.customer.get_full_name(),
        'status': order.status,
        'status_display': order.get_status_display(),
        'delivery_time': order.delivery_time,
        'delivery_date': order.delivery_date.isoformat(),
        'special_instructions': order.special_instructions,
        'subtotal': str(order.subtotal),
        'total_amount': str(order.total_amount),
        'created_at': order.created_at.isoformat(),
        'estimated_ready_time': order.get_estimated_ready_time().isoformat() if order.get_estimated_ready_time() else None,
        'is_delayed': order.is_delayed(),
        'can_cancel': order.can_be_cancelled(),
        'items': items_data,
        'items_count': order.get_items_count()
    }
    
    return JsonResponse(data)


@login_required
def reorder_items_api(request):
    """Get user's reorder items"""
    if not request.user.is_employee():
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    reorder_items = ReorderItem.objects.filter(
        user=request.user
    ).select_related('menu_item').order_by('-last_ordered')[:10]
    
    items_data = []
    for reorder_item in reorder_items:
        menu_item = reorder_item.menu_item
        items_data.append({
            'id': str(reorder_item.id),
            'menu_item_id': str(menu_item.id),
            'name': menu_item.name,
            'price': str(menu_item.get_display_price()),
            'quantity': reorder_item.quantity,
            'last_ordered': reorder_item.last_ordered.isoformat(),
            'order_count': reorder_item.order_count,
            'is_available': menu_item.is_available and menu_item.is_in_stock(),
            'image': menu_item.image.url if menu_item.image else None
        })
    
    return JsonResponse({'reorder_items': items_data})