import uuid
from decimal import Decimal
from apps.payments.models import WalletTransaction
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.http import JsonResponse, HttpResponseForbidden
from django.db.models import Sum, Count

from .models import Order, OrderItem, OrderHistory, ReorderItem, OrderQueue
from apps.menu.models import MenuItem
from apps.notifications.models import Notification


class OrderCheckoutForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ["full_name", "email", "phone_number", "office_number", "special_instructions"]


def is_canteen_admin(user):
    """Adjust to your User model (role field)."""
    return user.is_authenticated and (getattr(user, "role", None) == "canteen_admin" or user.is_superuser)


@login_required
def place_order(request):
    """
    Employee checkout form: collects contact details and items,
    creates an Order in PENDING status. Admin must VALIDATE before payment.
    """
    if request.method == "POST":
        form = OrderCheckoutForm(request.POST)
        if form.is_valid():
            # Create order skeleton
            order = form.save(commit=False)
            order.employee = request.user
            order.status = Order.STATUS_PENDING
            order.save()

            # Create items from posted inputs. Expect inputs named item_<menu_item_id> = quantity
            total = Decimal("0.00")
            created_any = False
            for key, value in request.POST.items():
                if key.startswith("item_"):
                    try:
                        menu_item_id = key.split("_", 1)[1]
                        qty = int(value)
                    except Exception:
                        continue
                    if qty <= 0:
                        continue
                    menu_item = get_object_or_404(MenuItem, id=menu_item_id)
                    oi = OrderItem.objects.create(order=order, menu_item=menu_item, quantity=qty, unit_price=menu_item.price)
                    total += oi.total
                    created_any = True

            if not created_any:
                # No items -> rollback and error
                order.delete()
                messages.error(request, "No items selected. Please select some items before placing an order.")
                return redirect("menu:view")  # menu template exists; keep behavior

            # Finalize totals (can contain tax/service logic)
            order.calculate_totals(save=True)

            # Log history
            OrderHistory.objects.create(order=order, status_from="", status_to=order.status, changed_by=request.user, notes="Order placed by employee")

            # Notify canteen admins (simple Notification, target_audience 'canteen_admins')
            Notification.objects.create(
                title=f"New order {order.order_number}",
                message=f"New order placed by {request.user.get_full_name() or request.user.username}. Please validate.",
                notification_type="order_status",
                priority="normal",
                target_audience="canteen_admins",
                order=order,
                created_by=request.user,
            )

            messages.success(request, "Order submitted! Awaiting canteen admin validation.")
            return redirect("orders:history")
    else:
        form = OrderCheckoutForm(initial={
            "full_name": f"{request.user.get_full_name() or request.user.username}",
            "email": getattr(request.user, "email", ""),
        })

    # Present menu items so user can choose quantities
    menu_items = MenuItem.objects.all().order_by("name")
    return render(request, "employee/create_order.html", {"form": form, "menu_items": menu_items})


@login_required
def order_history(request):
    """Display the logged-in employee's order history with stats."""
    employee = request.user  

    # Get all orders for this employee
    orders = (
        Order.objects.filter(employee=employee)
        .select_related("employee")
        .prefetch_related("items__menu_item", "history")
        .order_by("-created_at")
    )

    # Stats
    total_orders = orders.count()
    total_spent = orders.aggregate(total=Sum("total_amount"))["total"] or 0

    # Orders placed this month
    start_of_month = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monthly_orders = orders.filter(created_at__gte=start_of_month).count()

    # Pagination/load more (for future use)
    limit = int(request.GET.get("limit", 10))
    paginated_orders = orders[:limit]
    has_more_orders = orders.count() > limit

    context = {
        "orders": paginated_orders,
        "total_orders": total_orders,
        "monthly_orders": monthly_orders,
        "total_spent": total_spent,
        "has_more_orders": has_more_orders,
    }
    return render(request, "employee/order_history.html", context)


@login_required
def order_detail(request, order_id):
    """Return an HTML fragment for the modal or JSON data for AJAX."""
    order = get_object_or_404(Order, id=order_id)

    # Security: only employee who owns it or canteen_admin / superuser can view
    if not (request.user == order.employee or is_canteen_admin(request.user) or request.user.is_superuser):
        return HttpResponseForbidden("Not allowed")

    # If AJAX wanted JSON:
    if request.is_ajax() or request.headers.get("x-requested-with") == "XMLHttpRequest":
        items = [{
            "name": it.menu_item.name,
            "quantity": it.quantity,
            "unit_price": float(it.unit_price),
            "total": float(it.total)
        } for it in order.items.all()]
        data = {
            "order_number": order.order_number,
            "status": order.status,
            "items": items,
            "subtotal": float(order.subtotal),
            "total": float(order.total_amount),
            "special_instructions": order.special_instructions,
        }
        return JsonResponse(data)

    # Otherwise render a template fragment for the modal (create partial at templates/orders/partials/order_detail.html)
    return render(request, "employee/order_detail.html", {"order": order})


@login_required
def quick_order(request, item_id=None):
    """
    Create a simple 'quick order' for an employee without going through the full place_order form.
    - If `item_id` is given, order just that item.
    - Otherwise, show menu for selection.
    """

    if request.method == "POST":
        item_id = request.POST.get("item_id")
        menu_item = get_object_or_404(MenuItem, id=item_id)

        # Create a new order
        order = Order.objects.create(
            employee=request.user,
            full_name=request.user.get_full_name() or request.user.username,
            email=request.user.email,
            phone_number="N/A",   # you can extend later
            office_number="N/A",
            status="pending",
            subtotal=menu_item.price,
            total_amount=menu_item.price,  # taxes/fees can be added later
        )

        # Attach item
        order.items.create(
            order=order,
            product=menu_item,
            quantity=1,
            price=menu_item.price
        )

        messages.success(request, f"Quick order placed for {menu_item.name}. Waiting for validation.")
        return redirect("order_history")  # redirect to employeeâ€™s order history

    # GET request â†’ show quick order menu
    menu_items = MenuItem.objects.all()
    return render(request, "employee/quick_order.html", {"menu_items": menu_items})


@login_required
def add_to_cart(request, item_id):
    """
    Add a menu item to the employee's current cart (an order with 'pending' status).
    If no pending order exists, create one.
    """

    # Get the menu item
    menu_item = get_object_or_404(MenuItem, id=item_id)

    # Find or create a pending order for this employee
    order, created = Order.objects.get_or_create(
        employee=request.user,
        status="pending",
        defaults={
            "full_name": request.user.get_full_name() or request.user.username,
            "email": request.user.email,
            "phone_number": "N/A",
            "office_number": "N/A",
            "subtotal": 0,
            "total_amount": 0,
        }
    )

    # Add item to order items
    order_item = order.items.create(
        order=order,
        product=menu_item,
        quantity=1,
        price=menu_item.price
    )

    # Update totals
    order.subtotal += menu_item.price
    order.total_amount += menu_item.price
    order.save()

    messages.success(request, f"{menu_item.name} added to your cart.")
    return redirect("order_history")  # Or wherever you want to send the user




@login_required
def process_topup(request):
    """
    Allow employee to top up their wallet balance.
    For now we simulate the topup (e.g., via cash or external payment).
    """

    if request.method == "POST":
        amount = request.POST.get("amount")

        try:
            amount = Decimal(amount)
            if amount <= 0:
                raise ValueError("Amount must be positive")

            # Create wallet transaction
            WalletTransaction.objects.create(
                employee=request.user,
                amount=amount,
                transaction_type="credit",
                description="Wallet Top-up",
                created_at=timezone.now(),
            )

            messages.success(request, f"Wallet successfully topped up with {amount} XAF.")
            return redirect("employee_dashboard")

        except Exception as e:
            messages.error(request, f"Invalid amount: {e}")

    return render(request, "employee/process_topup.html")

@login_required
@user_passes_test(is_canteen_admin)
def orders_management(request):
    """Canteen admin view showing pending orders to validate/cancel."""
    pending = Order.objects.filter(status=Order.STATUS_PENDING).order_by("created_at")
    validated = Order.objects.filter(status=Order.STATUS_VALIDATED).order_by("-validated_at")[:30]
    return render(request, "canteen_admin/orders_management.html", {"pending_orders": pending, "validated_orders": validated})


@login_required
@user_passes_test(is_canteen_admin)
def validate_order(request, order_id):
    """Mark an order VALIDATED and notify the employee with a payment link."""
    order = get_object_or_404(Order, id=order_id, status=Order.STATUS_PENDING)
    order.status = Order.STATUS_VALIDATED
    order.validated_at = timezone.now()
    order.save()

    # Log history
    OrderHistory.objects.create(order=order, status_from=Order.STATUS_PENDING, status_to=Order.STATUS_VALIDATED, changed_by=request.user, notes="Validated by canteen admin")

    # Build payment link to send to employee (points back to proceed_to_payment view)
    payment_link = request.build_absolute_uri(reverse("orders:proceed_to_payment", args=[order.id]))

    # Create notification for the employee
    Notification.objects.create(
        title=f"Order {order.order_number} validated",
        message=f"Your order has been validated. Continue to payment: {payment_link}",
        notification_type="order_status",
        priority="normal",
        target_audience="specific_user",
        target_user=order.employee,
        order=order,
        created_by=request.user
    )

    messages.success(request, f"Order {order.order_number} validated and employee notified.")
    return redirect("orders:manage")


@login_required
@user_passes_test(is_canteen_admin)
def cancel_order(request, order_id):
    """Cancel a PENDING order (canteen admin)."""
    order = get_object_or_404(Order, id=order_id, status=Order.STATUS_PENDING)
    order.status = Order.STATUS_CANCELLED
    order.cancelled_at = timezone.now()
    order.save()

    OrderHistory.objects.create(order=order, status_from=Order.STATUS_PENDING, status_to=Order.STATUS_CANCELLED, changed_by=request.user, notes="Cancelled by canteen admin")

    # Notify employee about cancellation
    Notification.objects.create(
        title=f"Order {order.order_number} cancelled",
        message=f"Your order {order.order_number} was cancelled by the canteen admin.",
        notification_type="order_cancelled",
        priority="normal",
        target_audience="specific_user",
        target_user=order.employee,
        order=order,
        created_by=request.user
    )

    messages.error(request, f"Order {order.order_number} cancelled.")
    return redirect("orders:manage")


@login_required
def proceed_to_payment(request, order_id):
    """
    Entry point for the employee after order is validated.
    - If payments:process_payment exists in your payments app we redirect with ?order_id=...
    - Otherwise we render a simple confirmation page with a 'Pay now' button that posts to payments.
    """
    order = get_object_or_404(Order, id=order_id)

    # Only employee or admins can use this
    if not (request.user == order.employee or is_canteen_admin(request.user) or request.user.is_superuser):
        return HttpResponseForbidden("Not allowed")

    if order.status != Order.STATUS_VALIDATED:
        messages.error(request, "Order is not validated yet.")
        return redirect("orders:history")

    # If you have a payments route named 'payments:process_payment' accept a redirect with order_id
    try:
        payments_url = reverse("payments:process_payment")
        # Redirect user to the payments flow with order_id as query param
        return redirect(f"{payments_url}?order_id={order.id}")
    except Exception:
        # If payments endpoint not present, render a simple page instructing next steps.
        return render(request, "employee/proceed_to_payment.html", {"order": order})

@login_required
def get_cart(request):
    """
    Get current cart contents from session
    Returns cart data as JSON for AJAX requests
    """
    try:
        cart_items = request.session.get('cart_items', {})
        cart_data = []
        cart_total = Decimal('0.00')
        cart_count = 0
        
        # Process each item in cart
        for menu_item_id, quantity in cart_items.items():
            try:
                # Get menu item from database
                menu_item = MenuItem.objects.get(id=menu_item_id, is_available=True)
                
                # Calculate totals
                item_total = menu_item.price * quantity
                cart_total += item_total
                cart_count += quantity
                
                # Prepare item data
                cart_data.append({
                    'id': str(menu_item.id),
                    'name': menu_item.name,
                    'description': menu_item.description[:50] + '...' if len(menu_item.description) > 50 else menu_item.description,
                    'price': float(menu_item.price),
                    'quantity': quantity,
                    'total': float(item_total),
                    'image_url': menu_item.image.url if menu_item.image else None,
                    'category': menu_item.category.name,
                    'preparation_time': menu_item.preparation_time,
                    'is_available': menu_item.is_available,
                    'dietary_tags': menu_item.dietary_tags or []
                })
                
            except MenuItem.DoesNotExist:
                # Remove invalid item from cart
                continue
            except Exception as e:
                # Log error and continue with other items
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Error processing cart item {menu_item_id}: {str(e)}")
                continue
        
        # Clean up invalid items from session if any were found
        valid_items = {item['id']: cart_items[item['id']] for item in cart_data}
        if len(valid_items) != len(cart_items):
            request.session['cart_items'] = valid_items
            request.session.modified = True
        
        # Calculate service fee and total
        service_fee = cart_total * Decimal('0.05')  # 5% service fee
        final_total = cart_total + service_fee
        
        return JsonResponse({
            'success': True,
            'cart_items': cart_data,
            'cart_count': cart_count,
            'subtotal': float(cart_total),
            'service_fee': float(service_fee),
            'cart_total': float(final_total),
            'is_empty': len(cart_data) == 0,
            'message': f'{cart_count} item{"s" if cart_count != 1 else ""} in cart' if cart_count > 0 else 'Cart is empty'
        })
        
    except Exception as e:
        # Handle unexpected errors
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error retrieving cart: {str(e)}")
        
        return JsonResponse({
            'success': False,
            'error': 'Unable to retrieve cart contents',
            'cart_items': [],
            'cart_count': 0,
            'subtotal': 0,
            'service_fee': 0,
            'cart_total': 0,
            'is_empty': True
        }, status=500)


@login_required 
def get_cart_count(request):
    """
    Simple endpoint to just get cart item count
    Used for navbar badge updates
    """
    try:
        cart_items = request.session.get('cart_items', {})
        cart_count = sum(cart_items.values()) if cart_items else 0
        
        return JsonResponse({
            'success': True,
            'cart_count': cart_count
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'cart_count': 0,
            'error': str(e)
        }, status=500)


@login_required
def validate_cart(request):
    """
    Validate cart items before checkout
    Check availability, stock, and pricing
    """
    try:
        cart_items = request.session.get('cart_items', {})
        
        if not cart_items:
            return JsonResponse({
                'success': False,
                'message': 'Cart is empty',
                'valid': False
            })
        
        validation_results = []
        total_issues = 0
        
        for menu_item_id, quantity in cart_items.items():
            try:
                menu_item = MenuItem.objects.get(id=menu_item_id)
                issues = []
                
                # Check availability
                if not menu_item.is_available:
                    issues.append('Item is no longer available')
                    total_issues += 1
                
                # Check stock if applicable
                if hasattr(menu_item, 'current_stock') and menu_item.current_stock < quantity:
                    issues.append(f'Only {menu_item.current_stock} items in stock')
                    total_issues += 1
                
                # Check quantity limits
                if quantity > 10:  # Example limit
                    issues.append('Quantity exceeds maximum limit (10)')
                    total_issues += 1
                
                validation_results.append({
                    'item_id': str(menu_item.id),
                    'item_name': menu_item.name,
                    'quantity': quantity,
                    'price': float(menu_item.price),
                    'issues': issues,
                    'is_valid': len(issues) == 0
                })
                
            except MenuItem.DoesNotExist:
                validation_results.append({
                    'item_id': menu_item_id,
                    'item_name': 'Unknown Item',
                    'quantity': quantity,
                    'issues': ['Item no longer exists'],
                    'is_valid': False
                })
                total_issues += 1
        
        return JsonResponse({
            'success': True,
            'valid': total_issues == 0,
            'total_issues': total_issues,
            'validation_results': validation_results,
            'message': 'Cart is valid' if total_issues == 0 else f'Found {total_issues} issue(s) with cart items'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Validation error: {str(e)}',
            'valid': False
        }, status=500)

# Add these functions to your existing views.py file

@login_required
def update_cart(request):
    """
    Update cart quantities via AJAX
    """
    if request.method == "POST":
        try:
            import json
            data = json.loads(request.body)
            cart_items = data.get('cart_items', {})
            
            # Validate cart items
            validated_cart = {}
            for menu_item_id, quantity in cart_items.items():
                try:
                    menu_item = MenuItem.objects.get(id=menu_item_id)
                    if menu_item.is_available and quantity > 0:
                        validated_cart[menu_item_id] = int(quantity)
                except MenuItem.DoesNotExist:
                    continue
            
            # Update session
            request.session['cart_items'] = validated_cart
            request.session.modified = True
            
            return JsonResponse({
                'success': True,
                'message': 'Cart updated successfully'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=500)
    
    return JsonResponse({'success': False, 'message': 'Method not allowed'}, status=405)


@login_required
def clear_cart(request):
    """
    Clear the cart
    """
    if request.method == "POST":
        try:
            if 'cart_items' in request.session:
                del request.session['cart_items']
                request.session.modified = True
            
            return JsonResponse({
                'success': True,
                'message': 'Cart cleared successfully'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=500)
    
    return JsonResponse({'success': False, 'message': 'Method not allowed'}, status=405)


@login_required
def add_to_cart_ajax(request, item_id):
    """
    Add item to cart via AJAX (session-based since localStorage not available)
    This is the AJAX version of add_to_cart for the menu page
    """
    if request.method == "POST":
        try:
            menu_item = get_object_or_404(MenuItem, id=item_id)
            
            if not menu_item.is_available:
                return JsonResponse({
                    'success': False,
                    'message': 'Item is not available'
                }, status=400)
            
            quantity = int(request.POST.get('quantity', 1))
            if quantity <= 0:
                return JsonResponse({
                    'success': False,
                    'message': 'Invalid quantity'
                }, status=400)
            
            # Get or create cart in session
            cart_items = request.session.get('cart_items', {})
            
            # Add or update item in cart
            item_id_str = str(item_id)
            if item_id_str in cart_items:
                cart_items[item_id_str] += quantity
            else:
                cart_items[item_id_str] = quantity
            
            # Update session
            request.session['cart_items'] = cart_items
            request.session.modified = True
            
            # Calculate cart totals
            cart_total = Decimal('0.00')
            cart_count = 0
            for menu_id, qty in cart_items.items():
                try:
                    item = MenuItem.objects.get(id=menu_id)
                    cart_total += item.price * qty
                    cart_count += qty
                except MenuItem.DoesNotExist:
                    continue
            
            return JsonResponse({
                'success': True,
                'message': f'{menu_item.name} added to cart',
                'cart_count': cart_count,
                'cart_total': float(cart_total)
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=500)
    
    return JsonResponse({'success': False, 'message': 'Method not allowed'}, status=405)


@login_required
def create_order_from_cart(request):
    """
    Create order form view that shows items from cart
    This replaces the direct place_order for the new workflow
    """
    # Check if user has items in cart/session
    cart_items = request.session.get('cart_items', {})
    
    if not cart_items:
        messages.error(request, "No items selected. Please select some items from the menu first.")
        return redirect("menu:employee_menu")
    
    if request.method == "POST":
        form = OrderCheckoutForm(request.POST)
        if form.is_valid():
            return process_order_from_cart(request, form, cart_items)
    else:
        form = OrderCheckoutForm(initial={
            "full_name": f"{request.user.get_full_name() or request.user.username}",
            "email": getattr(request.user, "email", ""),
        })

    # Calculate order totals for display
    total_amount = Decimal("0.00")
    order_items = []
    
    for menu_item_id, quantity in cart_items.items():
        try:
            menu_item = MenuItem.objects.get(id=menu_item_id)
            item_total = menu_item.price * quantity
            total_amount += item_total
            
            order_items.append({
                'menu_item': menu_item,
                'quantity': quantity,
                'total': item_total
            })
        except MenuItem.DoesNotExist:
            continue
    
    context = {
        'form': form,
        'order_items': order_items,
        'total_amount': total_amount,
    }
    
    return render(request, "employee/create_order.html", context)


def process_order_from_cart(request, form, cart_items):
    """
    Process the order form submission from cart
    """
    try:
        from django.core.mail import send_mail
        from django.template.loader import render_to_string
        from django.conf import settings
        
        # Create order skeleton
        order = form.save(commit=False)
        order.employee = request.user
        order.status = Order.STATUS_PENDING
        order.save()

        # Create items from cart
        total = Decimal("0.00")
        created_any = False
        
        for menu_item_id, quantity in cart_items.items():
            try:
                menu_item = MenuItem.objects.get(id=menu_item_id)
                if quantity <= 0:
                    continue
                    
                order_item = OrderItem.objects.create(
                    order=order, 
                    menu_item=menu_item, 
                    quantity=quantity, 
                    unit_price=menu_item.price
                )
                total += order_item.total
                created_any = True
            except MenuItem.DoesNotExist:
                continue

        if not created_any:
            # No valid items -> rollback and error
            order.delete()
            messages.error(request, "No valid items found. Please try again.")
            return redirect("menu:employee_menu")

        # Finalize totals
        order.calculate_totals(save=True)

        # Log history
        OrderHistory.objects.create(
            order=order, 
            status_from="", 
            status_to=order.status, 
            changed_by=request.user, 
            notes="Order placed by employee"
        )

        # Send email to canteen admins (if configured)
        try:
            send_order_notification_email(order, request)
        except Exception as e:
            # Log error but don't fail the order creation
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to send order notification email: {str(e)}")

        # Create in-app notification for canteen admins
        Notification.objects.create(
            title=f"New order {order.order_number}",
            message=f"New order placed by {request.user.get_full_name() or request.user.username}. Please validate.",
            notification_type="order_status",
            priority="normal",
            target_audience="canteen_admins",
            order=order,
            created_by=request.user,
        )

        # Clear cart from session
        if 'cart_items' in request.session:
            del request.session['cart_items']
            request.session.modified = True

        messages.success(request, f"Order {order.order_number} submitted successfully! Awaiting canteen admin validation.")
        return redirect("orders:detail", order_id=order.id)
        
    except Exception as e:
        messages.error(request, f"Error creating order: {str(e)}")
        return redirect("menu:employee_menu")


def send_order_notification_email(order, request):
    """
    Send email notification to canteen admins about new order
    Only sends if email settings are configured
    """
    try:
        from django.contrib.auth import get_user_model
        from django.conf import settings
        
        # Only proceed if email settings exist
        if not hasattr(settings, 'EMAIL_HOST') or not settings.DEFAULT_FROM_EMAIL:
            return
        
        User = get_user_model()
        
        # Get canteen admin emails
        admin_emails = []
        canteen_admins = User.objects.filter(role='canteen_admin', is_active=True)
        for admin in canteen_admins:
            if admin.email:
                admin_emails.append(admin.email)
        
        # Also include superuser emails
        superusers = User.objects.filter(is_superuser=True, is_active=True)
        for admin in superusers:
            if admin.email and admin.email not in admin_emails:
                admin_emails.append(admin.email)
        
        if not admin_emails:
            return
        
        # Prepare email content
        subject = f"New Order #{order.order_number} - Validation Required"
        
        # Simple plain text email (can be enhanced with HTML template later)
        message = f"""
New Order Notification

Order Number: {order.order_number}
Customer: {order.employee.get_full_name() or order.employee.username}
Email: {order.email}
Phone: {order.phone_number}
Office: {order.office_number}
Total Amount: {order.total_amount} XAF

Items Ordered:
{chr(10).join([f"- {item.menu_item.name} x{item.quantity} = {item.total} XAF" for item in order.items.all()])}

Special Instructions: {order.special_instructions or 'None'}

Please log in to the admin panel to validate or cancel this order.

Thank you,
Enterprise Canteen System
        """
        
        # Send email
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=admin_emails,
            fail_silently=True  # Don't break order creation if email fails
        )
        
    except Exception as e:
        # Log error but don't break order creation
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to send order notification email: {str(e)}")