import uuid
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.http import JsonResponse, HttpResponseForbidden

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
    return render(request, "orders/checkout_form.html", {"form": form, "menu_items": menu_items})


@login_required
def order_history(request):
    """Show the current user's orders (simple pagination)."""
    page = int(request.GET.get("page", 1))
    page_size = 12
    offset = (page - 1) * page_size
    orders_qs = Order.objects.filter(employee=request.user).order_by("-created_at")
    total = orders_qs.count()
    orders = orders_qs[offset: offset + page_size]
    has_more = (offset + page_size) < total

    return render(request, "orders/order_history.html", {
        "orders": orders,
        "has_more_orders": has_more,
        "page": page,
    })


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
    return render(request, "orders/partials/order_detail.html", {"order": order})


@login_required
@user_passes_test(is_canteen_admin)
def orders_management(request):
    """Canteen admin view showing pending orders to validate/cancel."""
    pending = Order.objects.filter(status=Order.STATUS_PENDING).order_by("created_at")
    validated = Order.objects.filter(status=Order.STATUS_VALIDATED).order_by("-validated_at")[:30]
    return render(request, "orders/orders_management.html", {"pending_orders": pending, "validated_orders": validated})


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
        return render(request, "orders/proceed_to_payment.html", {"order": order})
