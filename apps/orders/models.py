from django.db import models
from django.core.validators import MinValueValidator
from django.conf import settings
from django.utils import timezone
from datetime import datetime, timedelta
import uuid

class Order(models.Model):
    """Main order model"""
    
    STATUS_CHOICES = settings.CANTEEN_SETTINGS['ORDER_STATUSES']
    
    DELIVERY_CHOICES = settings.CANTEEN_SETTINGS['DELIVERY_TIMES']
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(max_length=20, unique=True, db_index=True)
    
    # Customer information
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='orders'
    )
    
    # Order details
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='pending'
    )
    delivery_time = models.CharField(
        max_length=10,
        choices=DELIVERY_CHOICES,
        help_text="Preferred delivery time"
    )
    delivery_date = models.DateField(default=timezone.now)
    
    # Pricing
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Special requests and notes
    special_instructions = models.TextField(blank=True)
    internal_notes = models.TextField(
        blank=True,
        help_text="Internal notes for canteen staff"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(blank=True, null=True)
    prepared_at = models.DateTimeField(blank=True, null=True)
    ready_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    cancelled_at = models.DateTimeField(blank=True, null=True)
    
    # Staff assignments
    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='prepared_orders'
    )
    
    # Estimated times
    estimated_prep_time = models.PositiveIntegerField(
        default=15,
        help_text="Estimated preparation time in minutes"
    )
    actual_prep_time = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text="Actual preparation time in minutes"
    )
    
    # Ratings and feedback
    customer_rating = models.PositiveIntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(1), validators.MaxValueValidator(5)]
    )
    customer_feedback = models.TextField(blank=True)
    feedback_date = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        db_table = 'order'
        verbose_name = 'Order'
        verbose_name_plural = 'Orders'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order_number']),
            models.Index(fields=['customer', 'status']),
            models.Index(fields=['status', 'delivery_date']),
            models.Index(fields=['delivery_date', 'delivery_time']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Order #{self.order_number} - {self.customer.get_short_name()}"
    
    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self.generate_order_number()
        super().save(*args, **kwargs)
    
    def generate_order_number(self):
        """Generate unique order number"""
        today = timezone.now()
        date_str = today.strftime("%Y%m%d")
        
        # Get last order number for today
        last_order = Order.objects.filter(
            order_number__startswith=f"ORD{date_str}"
        ).order_by('-order_number').first()
        
        if last_order:
            last_number = int(last_order.order_number[-3:])
            new_number = last_number + 1
        else:
            new_number = 1
        
        return f"ORD{date_str}{new_number:03d}"
    
    def calculate_totals(self):
        """Calculate order totals"""
        items_total = self.items.aggregate(
            total=models.Sum(
                models.F('quantity') * models.F('unit_price'),
                output_field=models.DecimalField()
            )
        )['total'] or 0
        
        self.subtotal = items_total
        self.tax_amount = 0  # No tax in this implementation
        self.total_amount = self.subtotal - self.discount_amount
        self.save(update_fields=['subtotal', 'tax_amount', 'total_amount'])
    
    def can_be_cancelled(self):
        """Check if order can be cancelled"""
        if self.status in ['completed', 'cancelled']:
            return False
        
        # Allow cancellation up to 30 minutes before delivery time
        if self.delivery_date == timezone.now().date():
            delivery_datetime = datetime.combine(
                self.delivery_date,
                datetime.strptime(self.delivery_time, '%H:%M').time()
            )
            cutoff_time = delivery_datetime - timedelta(minutes=30)
            return timezone.now() < timezone.make_aware(cutoff_time)
        
        return True
    
    def get_status_color(self):
        """Get Bootstrap color class for order status"""
        status_colors = {
            'pending': 'warning',
            'confirmed': 'info',
            'preparing': 'primary',
            'ready': 'success',
            'completed': 'success',
            'cancelled': 'danger'
        }
        return status_colors.get(self.status, 'secondary')
    
    def get_status_icon(self):
        """Get Bootstrap icon for order status"""
        status_icons = {
            'pending': 'bi-clock',
            'confirmed': 'bi-check-circle',
            'preparing': 'bi-gear',
            'ready': 'bi-bell',
            'completed': 'bi-check2-all',
            'cancelled': 'bi-x-circle'
        }
        return status_icons.get(self.status, 'bi-question-circle')
    
    def update_status(self, new_status, user=None):
        """Update order status with timestamp tracking"""
        old_status = self.status
        self.status = new_status
        
        now = timezone.now()
        
        if new_status == 'confirmed' and old_status == 'pending':
            self.confirmed_at = now
        elif new_status == 'preparing' and old_status == 'confirmed':
            self.prepared_at = now
        elif new_status == 'ready' and old_status == 'preparing':
            self.ready_at = now
            # Calculate actual prep time
            if self.prepared_at:
                prep_time = (now - self.prepared_at).total_seconds() / 60
                self.actual_prep_time = int(prep_time)
        elif new_status == 'completed' and old_status == 'ready':
            self.completed_at = now
        elif new_status == 'cancelled':
            self.cancelled_at = now
        
        if user and user.can_manage_orders():
            self.prepared_by = user
        
        self.save()
        
        # Create status update notification
        self.create_status_notification(old_status, new_status)
    
    def create_status_notification(self, old_status, new_status):
        """Create notification for status change"""
        from apps.notifications.models import Notification
        
        status_messages = {
            'confirmed': f"Your order #{self.order_number} has been confirmed!",
            'preparing': f"Your order #{self.order_number} is being prepared.",
            'ready': f"Your order #{self.order_number} is ready for pickup!",
            'completed': f"Your order #{self.order_number} has been completed.",
            'cancelled': f"Your order #{self.order_number} has been cancelled."
        }
        
        if new_status in status_messages:
            Notification.objects.create(
                user=self.customer,
                title='Order Update',
                message=status_messages[new_status],
                notification_type='order_status',
                related_object_id=str(self.id)
            )
    
    def get_estimated_ready_time(self):
        """Calculate estimated ready time"""
        if self.confirmed_at:
            return self.confirmed_at + timedelta(minutes=self.estimated_prep_time)
        return None
    
    def is_delayed(self):
        """Check if order is delayed"""
        if self.status not in ['preparing', 'ready'] or not self.confirmed_at:
            return False
        
        estimated_time = self.get_estimated_ready_time()
        return timezone.now() > estimated_time
    
    def get_items_count(self):
        """Get total items count in order"""
        return self.items.aggregate(
            total=models.Sum('quantity')
        )['total'] or 0


class OrderItem(models.Model):
    """Individual items within an order"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items'
    )
    menu_item = models.ForeignKey(
        'menu.MenuItem',
        on_delete=models.CASCADE,
        related_name='order_items'
    )
    
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=8, decimal_places=2)
    total_price = models.DecimalField(max_digits=8, decimal_places=2)
    
    # Customizations
    special_instructions = models.TextField(blank=True)
    customizations = models.JSONField(
        default=dict,
        blank=True,
        help_text="Item customizations like spice level, extras, etc."
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'order_item'
        verbose_name = 'Order Item'
        verbose_name_plural = 'Order Items'
        ordering = ['id']
        indexes = [
            models.Index(fields=['order']),
            models.Index(fields=['menu_item']),
        ]
    
    def __str__(self):
        return f"{self.quantity}x {self.menu_item.name} - {self.order.order_number}"
    
    def save(self, *args, **kwargs):
        if not self.unit_price:
            self.unit_price = self.menu_item.get_display_price()
        
        self.total_price = self.quantity * self.unit_price
        super().save(*args, **kwargs)
        
        # Update order totals
        self.order.calculate_totals()
    
    def get_customizations_display(self):
        """Get formatted customizations for display"""
        if not self.customizations:
            return ""
        
        display_items = []
        for key, value in self.customizations.items():
            if value:
                display_items.append(f"{key.replace('_', ' ').title()}: {value}")
        
        return ", ".join(display_items)


class OrderQueue(models.Model):
    """Queue management for order preparation"""
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name='queue_item'
    )
    queue_position = models.PositiveIntegerField(default=0)
    priority = models.CharField(
        max_length=10, 
        choices=PRIORITY_CHOICES, 
        default='normal'
    )
    
    estimated_start_time = models.DateTimeField(blank=True, null=True)
    actual_start_time = models.DateTimeField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'order_queue'
        verbose_name = 'Order Queue Item'
        verbose_name_plural = 'Order Queue Items'
        ordering = ['priority', 'queue_position', 'created_at']
    
    def __str__(self):
        return f"Queue #{self.queue_position} - {self.order.order_number}"
    
    def move_up(self):
        """Move order up in queue"""
        if self.queue_position > 1:
            # Swap with previous item
            previous_item = OrderQueue.objects.filter(
                queue_position=self.queue_position - 1
            ).first()
            
            if previous_item:
                previous_item.queue_position += 1
                previous_item.save()
                
                self.queue_position -= 1
                self.save()
    
    def move_down(self):
        """Move order down in queue"""
        next_item = OrderQueue.objects.filter(
            queue_position=self.queue_position + 1
        ).first()
        
        if next_item:
            next_item.queue_position -= 1
            next_item.save()
            
            self.queue_position += 1
            self.save()


class OrderHistory(models.Model):
    """Track order status changes and history"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='history'
    )
    
    status_from = models.CharField(max_length=20, blank=True)
    status_to = models.CharField(max_length=20)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='order_changes'
    )
    
    notes = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'order_history'
        verbose_name = 'Order History'
        verbose_name_plural = 'Order Histories'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['order', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.order.order_number}: {self.status_from} → {self.status_to}"


class ReorderItem(models.Model):
    """Quick reorder functionality"""
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reorder_items'
    )
    menu_item = models.ForeignKey(
        'menu.MenuItem',
        on_delete=models.CASCADE,
        related_name='reorder_items'
    )
    
    quantity = models.PositiveIntegerField(default=1)
    last_ordered = models.DateTimeField(auto_now=True)
    order_count = models.PositiveIntegerField(default=1)
    
    class Meta:
        db_table = 'reorder_item'
        unique_together = ['user', 'menu_item']
        ordering = ['-last_ordered']
    
    def __str__(self):
        return f"{self.user.get_short_name()} - {self.menu_item.name}"
    
    def increment_order_count(self):
        """Increment order count"""
        self.order_count += 1
        self.last_ordered = timezone.now()
        self.save()


from django.core import validators