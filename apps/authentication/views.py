from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import View, TemplateView
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Sum, Q, Avg
from datetime import datetime, timedelta
from decimal import Decimal
from .models import SystemConfig
from apps.reports.models import AuditLog

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages

from .models import User, UserActivity
from apps.orders.models import Order, OrderItem
from apps.menu.models import MenuItem, MenuCategory
from apps.payments.models import Payment, WalletTransaction
from apps.notifications.models import Notification

def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        remember_me = request.POST.get("remember_me")  # will be "on" if checked

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            if remember_me:
                # Persistent session (e.g., 2 weeks)
                request.session.set_expiry(1209600)  # 2 weeks in seconds
            else:
                # Session ends when browser closes
                request.session.set_expiry(0)

            return redirect("dashboard")  # or wherever you want
        else:
            messages.error(request, "Invalid username or password")

    return render(request, "auth/login.html")

def contact_admin_reset(request):
    # Simple page telling user to contact system admin
    return render(request, "auth/contact_admin_reset.html")




class DashboardRedirectView(LoginRequiredMixin, View):
    """Redirect users to appropriate dashboard based on role"""
    
    def get(self, request):
        user = request.user
        if user.is_system_admin():
            return redirect('system_admin:dashboard')
        elif user.is_canteen_admin():
            return redirect('canteen_admin:dashboard')
        else:
            return redirect('employee:dashboard')


# Employee Dashboard Views
class EmployeeDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Employee dashboard with personal stats and quick actions"""
    template_name = 'employee/dashboard.html'
    
    def test_func(self):
        return self.request.user.is_employee() or self.request.user.is_superuser
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        today = timezone.now().date()
        this_month = today.replace(day=1)
        
        # Current orders (active orders)
        current_orders = Order.objects.filter(
            customer=user,
            status__in=['pending', 'confirmed', 'preparing', 'ready']
        ).order_by('-created_at')
        
        # Monthly statistics
        monthly_orders = Order.objects.filter(
            customer=user,
            created_at__date__gte=this_month
        ).count()
        
        # Personal statistics
        context.update({
            'current_orders_count': current_orders.count(),
            'monthly_orders': monthly_orders,
            'wallet_balance': user.wallet_balance,
            'favorite_items_count': user.favorite_items.count(),
            'current_orders': current_orders,
            'user': user,
        })
        
        # Today's specials
        todays_specials = MenuItem.objects.filter(
            is_special=True,
            is_available=True,
            special_until__gte=timezone.now()
        )[:4]
        context['todays_specials'] = todays_specials
        
        # Recent notifications
        recent_notifications = Notification.objects.filter(
            target_user=user
        ).select_related('target_user').order_by('-created_at')[:5]
        context['recent_notifications'] = recent_notifications
        
        # Unread notifications count
        unread_notifications = Notification.objects.filter(
            target_user=user,
            is_read=False
        ).count()
        context['unread_notifications'] = unread_notifications
        
        return context

def notifications_list(request):
    return render(request, "employee/notifications.html") 


def profile_view(request):
    return render(request, "auth/profile.html")  


def settings_view(request):
    return render(request, "auth/settings.html")  

def logout_confirm_view(request):
    """Show confirmation page before logout"""
    return render(request, "auth/logout.html")

def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect("auth/login.html")
    



class CanteenAdminDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Canteen admin dashboard with operational overview"""
    template_name = 'canteen_admin/dashboard.html'
    
    def test_func(self):
        return self.request.user.is_canteen_admin() or self.request.user.is_superuser
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        
        # Today's statistics
        todays_orders = Order.objects.filter(created_at__date=today)
        completed_orders = todays_orders.filter(status='completed')
        
        todays_revenue = completed_orders.aggregate(
            total=Sum('total_amount')
        )['total'] or Decimal('0.00')
        
        pending_orders = todays_orders.filter(
            status__in=['pending', 'confirmed', 'preparing']
        ).count()
        
        # Yesterday's comparison
        yesterday_orders = Order.objects.filter(created_at__date=yesterday).count()
        yesterday_revenue = Order.objects.filter(
            created_at__date=yesterday,
            status='completed'
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
        
        # Calculate percentage changes
        orders_change = 0
        if yesterday_orders > 0:
            orders_change = ((todays_orders.count() - yesterday_orders) / yesterday_orders) * 100
        
        revenue_percentage = 0
        if yesterday_revenue > 0:
            revenue_percentage = ((todays_revenue - yesterday_revenue) / yesterday_revenue) * 100
        
        # Low stock items
        low_stock_items = MenuItem.objects.filter(
            current_stock__lte=models.F('low_stock_threshold'),
            is_available=True
        ).count()
        
        # Average preparation time
        avg_prep_time = completed_orders.filter(
            actual_prep_time__isnull=False
        ).aggregate(avg=Avg('actual_prep_time'))['avg'] or 0
        
        # Daily target (example: 50 orders per day)
        daily_target = 50
        
        context.update({
            'todays_orders': todays_orders.count(),
            'todays_revenue': todays_revenue,
            'pending_orders': pending_orders,
            'low_stock_items': low_stock_items,
            'orders_change': orders_change,
            'daily_target': daily_target,
            'revenue_percentage': revenue_percentage,
            'avg_prep_time': avg_prep_time,
        })
        
        # Pending orders list for queue management
        pending_order_list = todays_orders.filter(
            status__in=['confirmed', 'preparing']
        ).select_related('customer').order_by('created_at')[:10]
        context['pending_order_list'] = pending_order_list
        
        # Additional stats for the dashboard
        active_employees = User.objects.filter(
            role='employee',
            status='active',
            last_activity__date=today
        ).count()
        
        # Average order completion time
        avg_order_time = completed_orders.filter(
            confirmed_at__isnull=False,
            completed_at__isnull=False
        ).annotate(
            completion_time=models.F('completed_at') - models.F('confirmed_at')
        ).aggregate(avg=Avg('completion_time'))['avg']
        
        if avg_order_time:
            avg_order_time = avg_order_time.total_seconds() / 60  # Convert to minutes
        else:
            avg_order_time = 0
        
        # Orders per hour calculation
        current_hour = timezone.now().hour
        orders_this_hour = todays_orders.filter(
            created_at__hour=current_hour
        ).count()
        
        # Completion rate
        completion_rate = 0
        if todays_orders.count() > 0:
            completion_rate = (completed_orders.count() / todays_orders.count()) * 100
        
        context.update({
            'active_employees': active_employees,
            'avg_order_time': round(avg_order_time, 1),
            'orders_per_hour': orders_this_hour,
            'completion_rate': round(completion_rate, 1),
        })
        
        # Top menu items
        top_menu_items = MenuItem.objects.filter(
            order_items__order__created_at__date=today,
            order_items__order__status='completed'
        ).annotate(
            orders_count=Count('order_items'),
            revenue=Sum(models.F('order_items__quantity') * models.F('order_items__unit_price'))
        ).order_by('-orders_count')[:5]
        context['top_menu_items'] = top_menu_items
        
        # Alerts
        alerts = []
        if low_stock_items > 0:
            alerts.append({
                'type': 'warning',
                'message': f'{low_stock_items} items are running low on stock'
            })
        if pending_orders > 10:
            alerts.append({
                'type': 'danger',
                'message': f'{pending_orders} orders are waiting to be processed'
            })
        context['alerts'] = alerts
        
        # Recent orders for the table
        recent_orders = todays_orders.select_related('customer').order_by('-created_at')[:10]
        context['recent_orders'] = recent_orders
        
        return context


class SystemAdminDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """System admin dashboard for user management"""
    template_name = 'system_admin/dashboard.html'
    
    def test_func(self):
        return self.request.user.is_system_admin() or self.request.user.is_superuser
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # User statistics
        total_users = User.objects.count()
        employees_count = User.objects.filter(role='employee').count()
        canteen_admins_count = User.objects.filter(role='canteen_admin').count()
        active_users_count = User.objects.filter(status='active').count()
        
        context.update({
            'total_users': total_users,
            'employees_count': employees_count,
            'canteen_admins_count': canteen_admins_count,
            'active_users_count': active_users_count,
        })
        
        # Users list with search and filtering
        users_queryset = User.objects.select_related().order_by('-date_joined')
        
        # Apply filters if provided
        search = self.request.GET.get('search', '')
        role_filter = self.request.GET.get('role', '')
        status_filter = self.request.GET.get('status', '')
        
        if search:
            users_queryset = users_queryset.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search) |
                Q(employee_id__icontains=search)
            )
        
        if role_filter:
            users_queryset = users_queryset.filter(role=role_filter)
        
        if status_filter:
            users_queryset = users_queryset.filter(status=status_filter)
        
        context['users'] = users_queryset[:50]  # Limit for performance
        context['search'] = search
        context['role_filter'] = role_filter
        context['status_filter'] = status_filter
        
        return context

User = get_user_model()


# -------------------------
# User Management Dashboard
# -------------------------
def UserManagementView(request):
    """System Admin - Manage Users"""

    # Statistics
    total_users = User.objects.count()
    employees_count = User.objects.filter(role="employee").count()
    canteen_admins_count = User.objects.filter(role="canteen_admin").count()
    active_users_count = User.objects.filter(is_active=True).count()

    # List all users
    users = User.objects.all().order_by("-date_joined")

    context = {
        "total_users": total_users,
        "employees_count": employees_count,
        "canteen_admins_count": canteen_admins_count,
        "active_users_count": active_users_count,
        "users": users,
    }
    return render(request, "system_admin/user_management.html", context)


# -------------------------
# Create User
# -------------------------
def create_user_view(request):
    """System Admin - Create new user"""
    if request.method == "POST":
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        username = request.POST.get("username")
        email = request.POST.get("email")
        employee_id = request.POST.get("employee_id")
        department = request.POST.get("department")
        role = request.POST.get("role")
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")

        # Validation
        if not (first_name and last_name and username and email and role and password):
            messages.error(request, "All required fields must be filled.")
            return redirect("system_admin:user_management")

        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return redirect("system_admin:user_management")

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already exists.")
            return redirect("system_admin:user_management")

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return redirect("system_admin:user_management")

        # Create user
        user = User.objects.create(
            first_name=first_name,
            last_name=last_name,
            username=username,
            email=email,
            employee_id=employee_id,
            department=department,
            role=role,
            password=make_password(password),
            is_active=True,
        )

        messages.success(request, f"User {user.get_full_name()} created successfully.")
        return redirect("system_admin:user_management")

    return redirect("system_admin:user_management")


def is_system_admin(user):
    return user.is_authenticated and user.role == "system_admin"


def audit_logs_view(request):
    today = now().date()
    logs = AuditLog.objects.select_related("user").order_by("-timestamp")[:200]

    context = {
        "audit_logs": logs,
        "total_activities": AuditLog.objects.count(),
        "today_events": AuditLog.objects.filter(timestamp__date=today).count(),
        "active_users": AuditLog.objects.filter(timestamp__date=today).values("user").distinct().count(),
        "failed_logins": AuditLog.objects.filter(activity_type="failed_login", timestamp__date=today).count(),
    }
    return render(request, "audit_logs.html", context)


# Authentication Views
# Updated login_view function in views.py

def login_view(request):
    """Custom login view"""
    if request.user.is_authenticated:
        # Already logged in, redirect by role
        if request.user.is_superuser or request.user.role == "system_admin":
            return redirect("system_admin:dashboard")
        elif request.user.role == "canteen_admin":
            return redirect("canteen_admin:dashboard")
        elif request.user.role == "employee":
            return redirect("employee:dashboard")
        else:
            return redirect("dashboard")

    if request.method == 'POST':
        # Get username (can be email or actual username)
        username = request.POST.get('username')
        password = request.POST.get('password')

        if username and password:
            # Try authentication
            user = authenticate(request, username=username, password=password)
            
            if user is not None:
                # Check if account is locked
                if user.is_account_locked():
                    messages.error(request, 'Account is temporarily locked due to multiple failed login attempts.')
                    return render(request, 'auth/login.html')
                
                # Check if account is active
                if user.status != 'active':
                    messages.error(request, 'Your account is not active. Please contact administrator.')
                    return render(request, 'auth/login.html')
                
                # Login successful
                login(request, user)
                user.increment_login_count()
                user.update_last_activity()

                # Log user activity
                UserActivity.objects.create(
                    user=user,
                    activity_type='login',
                    description='User logged in successfully',
                    ip_address=get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')
                )

                # Success message
                messages.success(request, f'Welcome back, {user.get_full_name()}!')

                # Redirect based on 'next' parameter or user role
                next_url = request.GET.get('next') or request.POST.get('next')
                if next_url:
                    return redirect(next_url)

                # Role-based redirect
                if user.is_superuser or user.role == "system_admin":
                    return redirect("system_admin:dashboard")
                elif user.role == "canteen_admin":
                    return redirect("canteen_admin:dashboard")
                elif user.role == "employee":
                    return redirect("employee:dashboard")
                else:
                    return redirect("dashboard")

            else:
                # Authentication failed
                # Try to find user to increment failed attempts
                try:
                    # Try to find user by email or username
                    from django.db.models import Q
                    failed_user = User.objects.get(
                        Q(email=username) | Q(username=username)
                    )
                    failed_user.increment_failed_login()
                    
                    # Log failed attempt
                    UserActivity.objects.create(
                        user=failed_user,
                        activity_type='login',
                        description='Failed login attempt',
                        ip_address=get_client_ip(request),
                        user_agent=request.META.get('HTTP_USER_AGENT', '')
                    )
                    
                except User.DoesNotExist:
                    pass
                
                messages.error(request, 'Invalid credentials. Please check your username and password.')
        else:
            messages.error(request, 'Please provide both username and password.')

    return render(request, 'auth/login.html')



@login_required
def logout_view(request):
    """Custom logout view"""
    user = request.user
    
    # Log user activity
    UserActivity.objects.create(
        user=user,
        activity_type='logout',
        description='User logged out',
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')
    )
    
    logout(request)
    messages.info(request, 'You have been logged out successfully.')
    return redirect('auth:login')


# AJAX Views for real-time updates
@login_required
def refresh_employee_orders(request):
    """AJAX view to refresh employee orders"""
    if not request.user.is_employee():
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    current_orders = Order.objects.filter(
        customer=request.user,
        status__in=['pending', 'confirmed', 'preparing', 'ready']
    ).select_related('customer').prefetch_related('items__menu_item')
    
    orders_data = []
    for order in current_orders:
        orders_data.append({
            'id': str(order.id),
            'order_number': order.order_number,
            'status': order.status,
            'status_display': order.get_status_display(),
            'total_amount': str(order.total_amount),
            'created_at': order.created_at.strftime('%H:%M'),
            'can_cancel': order.can_be_cancelled(),
            'items_count': order.get_items_count(),
        })
    
    return JsonResponse({
        'orders': orders_data,
        'count': len(orders_data)
    })


@login_required
def canteen_admin_dashboard_data(request):
    """AJAX view for canteen admin dashboard real-time data"""
    if not request.user.is_canteen_admin():
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    today = timezone.now().date()
    todays_orders = Order.objects.filter(created_at__date=today)
    
    data = {
        'todays_orders': todays_orders.count(),
        'pending_orders': todays_orders.filter(
            status__in=['pending', 'confirmed', 'preparing']
        ).count(),
        'completed_orders': todays_orders.filter(status='completed').count(),
        'todays_revenue': str(todays_orders.filter(
            status='completed'
        ).aggregate(total=Sum('total_amount'))['total'] or 0),
    }
    
    return JsonResponse(data)

@login_required
def system_config(request):
    """System configuration page for system admins"""
    if not request.user.is_system_admin():
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    config, created = SystemConfig.objects.get_or_create(id=1)  # singleton pattern

    return render(request, "system_admin/system_config.html", {"config": config})


# Utility functions
def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


# Error handlers
def custom_404(request, exception):
    """Custom 404 error handler"""
    return render(request, 'errors/404.html', status=404)


def custom_500(request):
    """Custom 500 error handler"""
    return render(request, 'errors/500.html', status=500)


def custom_403(request, exception):
    """Custom 403 error handler"""
    return render(request, 'errors/403.html', status=403)