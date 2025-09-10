"""
Reports app models
File: apps/reports/models.py
"""
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.db.models import Sum, Count, Avg
import uuid

class Report(models.Model):
    """Generated reports model"""
    
    REPORT_TYPES = [
        ('daily_sales', 'Daily Sales Report'),
        ('weekly_sales', 'Weekly Sales Report'),
        ('monthly_sales', 'Monthly Sales Report'),
        ('menu_performance', 'Menu Performance Report'),
        ('user_activity', 'User Activity Report'),
        ('payment_summary', 'Payment Summary Report'),
        ('inventory_report', 'Inventory Report'),
        ('custom', 'Custom Report'),
    ]
    
    REPORT_FORMATS = [
        ('pdf', 'PDF'),
        ('excel', 'Excel'),
        ('csv', 'CSV'),
        ('json', 'JSON'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('generating', 'Generating'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    report_type = models.CharField(max_length=50, choices=REPORT_TYPES)
    format = models.CharField(max_length=20, choices=REPORT_FORMATS, default='pdf')
    
    # Report parameters
    date_from = models.DateField()
    date_to = models.DateField()
    filters = models.JSONField(default=dict, blank=True)
    
    # Generation details
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    file_path = models.FileField(upload_to='reports/', blank=True, null=True)
    file_size = models.PositiveIntegerField(blank=True, null=True)
    
    # Metadata
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='generated_reports'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    
    # Error tracking
    error_message = models.TextField(blank=True)
    
    class Meta:
        db_table = 'report'
        verbose_name = 'Report'
        verbose_name_plural = 'Reports'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['report_type']),
            models.Index(fields=['status']),
            models.Index(fields=['generated_by']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.get_report_type_display()}"
    
    def is_expired(self):
        """Check if report is expired"""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
    
    def get_generation_time(self):
        """Get report generation time in seconds"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    def mark_as_started(self):
        """Mark report generation as started"""
        self.status = 'generating'
        self.started_at = timezone.now()
        self.save()
    
    def mark_as_completed(self, file_path=None, file_size=None):
        """Mark report as completed"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        
        if file_path:
            self.file_path = file_path
        if file_size:
            self.file_size = file_size
        
        # Set expiration to 30 days from now
        from datetime import timedelta
        self.expires_at = timezone.now() + timedelta(days=30)
        
        self.save()
    
    def mark_as_failed(self, error_message=None):
        """Mark report generation as failed"""
        self.status = 'failed'
        if error_message:
            self.error_message = error_message
        self.save()


class DailySalesReport(models.Model):
    """Daily sales aggregation for quick reporting"""
    
    date = models.DateField(unique=True, db_index=True)
    
    # Order statistics
    total_orders = models.PositiveIntegerField(default=0)
    completed_orders = models.PositiveIntegerField(default=0)
    cancelled_orders = models.PositiveIntegerField(default=0)
    
    # Revenue statistics
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    gross_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    net_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    # Payment statistics
    wallet_payments = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    mtn_payments = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    orange_payments = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    # Customer statistics
    unique_customers = models.PositiveIntegerField(default=0)
    new_customers = models.PositiveIntegerField(default=0)
    repeat_customers = models.PositiveIntegerField(default=0)
    
    # Operational statistics
    average_order_value = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    average_prep_time = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    peak_hour = models.TimeField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'daily_sales_report'
        verbose_name = 'Daily Sales Report'
        verbose_name_plural = 'Daily Sales Reports'
        ordering = ['-date']
    
    def __str__(self):
        return f"Sales Report - {self.date}"
    
    @classmethod
    def generate_for_date(cls, date):
        """Generate daily sales report for specific date"""
        from apps.orders.models import Order
        from apps.payments.models import Payment
        from apps.authentication.models import User
        
        # Get orders for the date
        orders = Order.objects.filter(created_at__date=date)
        completed_orders = orders.filter(status='completed')
        
        # Calculate statistics
        total_orders = orders.count()
        completed_count = completed_orders.count()
        cancelled_count = orders.filter(status='cancelled').count()
        
        # Revenue calculations
        total_revenue = completed_orders.aggregate(
            total=Sum('total_amount')
        )['total'] or 0
        
        # Payment method breakdown
        payments = Payment.objects.filter(
            created_at__date=date,
            status='completed'
        )
        
        payment_breakdown = payments.values('payment_method').annotate(
            total=Sum('amount')
        )
        
        wallet_payments = 0
        mtn_payments = 0
        orange_payments = 0
        
        for payment in payment_breakdown:
            if payment['payment_method'] == 'wallet':
                wallet_payments = payment['total']
            elif payment['payment_method'] == 'mtn':
                mtn_payments = payment['total']
            elif payment['payment_method'] == 'orange':
                orange_payments = payment['total']
        
        # Customer statistics
        customer_orders = completed_orders.values('customer').distinct()
        unique_customers = customer_orders.count()
        
        # Average order value
        avg_order_value = completed_orders.aggregate(
            avg=Avg('total_amount')
        )['avg'] or 0
        
        # Average prep time
        avg_prep_time = completed_orders.filter(
            actual_prep_time__isnull=False
        ).aggregate(
            avg=Avg('actual_prep_time')
        )['avg'] or 0
        
        # Create or update the report
        report, created = cls.objects.update_or_create(
            date=date,
            defaults={
                'total_orders': total_orders,
                'completed_orders': completed_count,
                'cancelled_orders': cancelled_count,
                'total_revenue': total_revenue,
                'gross_revenue': total_revenue,
                'net_revenue': total_revenue,  # Assuming no additional costs
                'wallet_payments': wallet_payments,
                'mtn_payments': mtn_payments,
                'orange_payments': orange_payments,
                'unique_customers': unique_customers,
                'average_order_value': avg_order_value,
                'average_prep_time': avg_prep_time,
            }
        )
        
        return report


class MenuItemPerformance(models.Model):
    """Menu item performance analytics"""
    
    menu_item = models.ForeignKey(
        'menu.MenuItem',
        on_delete=models.CASCADE,
        related_name='performance_reports'
    )
    date = models.DateField(db_index=True)
    
    # Sales metrics
    orders_count = models.PositiveIntegerField(default=0)
    quantity_sold = models.PositiveIntegerField(default=0)
    revenue = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Performance metrics
    conversion_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0.00,
        help_text="Percentage of views that resulted in orders"
    )
    average_rating = models.DecimalField(
        max_digits=3, 
        decimal_places=2, 
        default=0.00
    )
    
    # Ranking
    popularity_rank = models.PositiveIntegerField(blank=True, null=True)
    revenue_rank = models.PositiveIntegerField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'menu_item_performance'
        unique_together = ['menu_item', 'date']
        verbose_name = 'Menu Item Performance'
        verbose_name_plural = 'Menu Item Performance Reports'
        ordering = ['-date', '-revenue']
        indexes = [
            models.Index(fields=['date', 'revenue']),
            models.Index(fields=['date', 'quantity_sold']),
        ]
    
    def __str__(self):
        return f"{self.menu_item.name} - {self.date}"


class UserActivityReport(models.Model):
    """User activity analytics"""
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='activity_reports'
    )
    date = models.DateField(db_index=True)
    
    # Activity metrics
    login_count = models.PositiveIntegerField(default=0)
    orders_placed = models.PositiveIntegerField(default=0)
    total_spent = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Engagement metrics
    session_duration = models.DurationField(blank=True, null=True)
    pages_viewed = models.PositiveIntegerField(default=0)
    
    # Behavioral metrics
    favorite_items_added = models.PositiveIntegerField(default=0)
    reviews_given = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_activity_report'
        unique_together = ['user', 'date']
        verbose_name = 'User Activity Report'
        verbose_name_plural = 'User Activity Reports'
        ordering = ['-date', '-total_spent']
        indexes = [
            models.Index(fields=['date', 'orders_placed']),
            models.Index(fields=['date', 'total_spent']),
        ]
    
    def __str__(self):
        return f"{self.user.get_short_name()} - {self.date}"


class SystemAnalytics(models.Model):
    """System-wide analytics and KPIs"""
    
    date = models.DateField(unique=True, db_index=True)
    
    # User metrics
    total_users = models.PositiveIntegerField(default=0)
    active_users = models.PositiveIntegerField(default=0)
    new_users = models.PositiveIntegerField(default=0)
    
    # Order metrics
    total_orders = models.PositiveIntegerField(default=0)
    successful_orders = models.PositiveIntegerField(default=0)
    cancelled_orders = models.PositiveIntegerField(default=0)
    
    # Revenue metrics
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    average_order_value = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    
    # Performance metrics
    average_prep_time = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    order_completion_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    customer_satisfaction = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    
    # System metrics
    peak_concurrent_users = models.PositiveIntegerField(default=0)
    system_uptime = models.DecimalField(max_digits=5, decimal_places=2, default=100.00)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'system_analytics'
        verbose_name = 'System Analytics'
        verbose_name_plural = 'System Analytics'
        ordering = ['-date']
    
    def __str__(self):
        return f"System Analytics - {self.date}"
    
    @classmethod
    def generate_for_date(cls, date):
        """Generate system analytics for specific date"""
        from apps.authentication.models import User
        from apps.orders.models import Order
        
        # User metrics
        total_users = User.objects.count()
        active_users = User.objects.filter(
            last_activity__date=date
        ).count()
        new_users = User.objects.filter(
            date_joined__date=date
        ).count()
        
        # Order metrics
        orders = Order.objects.filter(created_at__date=date)
        total_orders = orders.count()
        successful_orders = orders.filter(status='completed').count()
        cancelled_orders = orders.filter(status='cancelled').count()
        
        # Revenue metrics
        completed_orders = orders.filter(status='completed')
        total_revenue = completed_orders.aggregate(
            total=Sum('total_amount')
        )['total'] or 0
        
        avg_order_value = completed_orders.aggregate(
            avg=Avg('total_amount')
        )['avg'] or 0
        
        # Performance metrics
        avg_prep_time = completed_orders.filter(
            actual_prep_time__isnull=False
        ).aggregate(
            avg=Avg('actual_prep_time')
        )['avg'] or 0
        
        completion_rate = 0
        if total_orders > 0:
            completion_rate = (successful_orders / total_orders) * 100
        
        # Create or update analytics
        analytics, created = cls.objects.update_or_create(
            date=date,
            defaults={
                'total_users': total_users,
                'active_users': active_users,
                'new_users': new_users,
                'total_orders': total_orders,
                'successful_orders': successful_orders,
                'cancelled_orders': cancelled_orders,
                'total_revenue': total_revenue,
                'average_order_value': avg_order_value,
                'average_prep_time': avg_prep_time,
                'order_completion_rate': completion_rate,
            }
        )
        
        return analytics


class ReportSubscription(models.Model):
    """Automated report subscriptions"""
    
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    report_type = models.CharField(max_length=50, choices=Report.REPORT_TYPES)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)  # ✅ completed here
    recipients = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="report_subscriptions"
    )
    is_active = models.BooleanField(default=True)
    last_sent_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "report_subscription"
        verbose_name = "Report Subscription"
        verbose_name_plural = "Report Subscriptions"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.frequency})"

class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="audit_logs")
    activity = models.CharField(max_length=100)   # e.g. "Login", "Logout", "Payment"
    description = models.TextField()              # Detailed description of the action
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.user} - {self.activity} at {self.timestamp}"
