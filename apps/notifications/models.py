from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid

class Notification(models.Model):
    """Main notification model for all system notifications"""
    
    NOTIFICATION_TYPE_CHOICES = [
        ('order_status', 'Order Status Update'),
        ('order_ready', 'Order Ready'),
        ('order_cancelled', 'Order Cancelled'),
        ('payment_success', 'Payment Successful'),
        ('payment_failed', 'Payment Failed'),
        ('menu_update', 'Menu Update'),
        ('system_announcement', 'System Announcement'),
        ('low_stock', 'Low Stock Alert'),
        ('wallet_topup', 'Wallet Top-up'),
        ('promotion', 'Promotion/Offer'),
        ('maintenance', 'System Maintenance'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    TARGET_AUDIENCE_CHOICES = [
        ('all_users', 'All Users'),
        ('employees', 'All Employees'),
        ('canteen_admins', 'Canteen Admins'),
        ('system_admins', 'System Admins'),
        ('specific_user', 'Specific User'),
        ('department', 'Specific Department'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Content
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPE_CHOICES, default='info')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal')
    
    # Targeting
    target_audience = models.CharField(max_length=20, choices=TARGET_AUDIENCE_CHOICES)
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name='targeted_notifications'
    )
    target_department = models.CharField(max_length=100, blank=True)
    
    # Related objects
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name='notifications'
    )
    payment = models.ForeignKey(
        'payments.Payment',
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name='notifications'
    )
    menu_item = models.ForeignKey(
        'menu.MenuItem',
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name='notifications'
    )
    
    # Delivery settings
    send_email = models.BooleanField(default=False)
    send_sms = models.BooleanField(default=False)
    send_push = models.BooleanField(default=True)
    
    # Status and timing
    is_active = models.BooleanField(default=True)
    is_scheduled = models.BooleanField(default=False)
    scheduled_at = models.DateTimeField(blank=True, null=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    
    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='created_notifications'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Analytics
    total_recipients = models.PositiveIntegerField(default=0)
    total_read = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'notifications_notification'
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['target_audience']),
            models.Index(fields=['notification_type']),
            models.Index(fields=['is_active', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.get_target_audience_display()})"
    
    @property
    def is_expired(self):
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
    
    @property
    def read_percentage(self):
        if self.total_recipients > 0:
            return round((self.total_read / self.total_recipients) * 100, 1)
        return 0
    
    def get_recipients(self):
        """Get list of users who should receive this notification"""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        if self.target_audience == 'all_users':
            return User.objects.filter(is_active=True)
        elif self.target_audience == 'employees':
            return User.objects.filter(is_active=True, role='employee')
        elif self.target_audience == 'canteen_admins':
            return User.objects.filter(is_active=True, role='canteen_admin')
        elif self.target_audience == 'system_admins':
            return User.objects.filter(is_active=True, role='system_admin')
        elif self.target_audience == 'specific_user' and self.target_user:
            return User.objects.filter(id=self.target_user.id)
        elif self.target_audience == 'department' and self.target_department:
            return User.objects.filter(is_active=True, department=self.target_department)
        return User.objects.none()


class UserNotification(models.Model):
    """Individual notification delivery and read status"""
    
    notification = models.ForeignKey(
        Notification,
        on_delete=models.CASCADE,
        related_name='user_notifications'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_notifications'
    )
    
    # Status
    is_read = models.BooleanField(default=False)
    is_dismissed = models.BooleanField(default=False)
    read_at = models.DateTimeField(blank=True, null=True)
    dismissed_at = models.DateTimeField(blank=True, null=True)
    
    # Delivery status
    email_sent = models.BooleanField(default=False)
    sms_sent = models.BooleanField(default=False)
    push_sent = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'notifications_user_notification'
        verbose_name = 'User Notification'
        verbose_name_plural = 'User Notifications'
        unique_together = ['notification', 'user']
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return f"{self.notification.title} -> {self.user.username}"
    
    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])
            
            # Update parent notification read count
            self.notification.total_read = self.notification.user_notifications.filter(is_read=True).count()
            self.notification.save(update_fields=['total_read'])
    
    def dismiss(self):
        self.is_dismissed = True
        self.dismissed_at = timezone.now()
        self.save(update_fields=['is_dismissed', 'dismissed_at'])


class NotificationTemplate(models.Model):
    """Predefined templates for common notifications"""
    
    name = models.CharField(max_length=100, unique=True)
    notification_type = models.CharField(max_length=20, choices=Notification.TYPE_CHOICES)
    title_template = models.CharField(max_length=255)
    message_template = models.TextField()
    priority = models.CharField(max_length=10, choices=Notification.PRIORITY_CHOICES, default='normal')
    
    # Default delivery settings
    default_send_email = models.BooleanField(default=False)
    default_send_sms = models.BooleanField(default=False)
    default_send_push = models.BooleanField(default=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'notifications_template'
        verbose_name = 'Notification Template'
        verbose_name_plural = 'Notification Templates'
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def render(self, context=None):
        """Render template with context variables"""
        if context is None:
            context = {}
        
        title = self.title_template
        message = self.message_template
        
        # Simple template variable replacement
        for key, value in context.items():
            title = title.replace(f'{{{key}}}', str(value))
            message = message.replace(f'{{{key}}}', str(value))
        
        return title, message


class NotificationPreference(models.Model):
    """User preferences for notification delivery"""
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_preferences'
    )
    
    # Global settings
    receive_email = models.BooleanField(default=True)
    receive_sms = models.BooleanField(default=False)
    receive_push = models.BooleanField(default=True)
    
    # Specific notification types
    order_updates = models.BooleanField(default=True)
    payment_updates = models.BooleanField(default=True)
    menu_updates = models.BooleanField(default=True)
    promotions = models.BooleanField(default=True)
    system_announcements = models.BooleanField(default=True)
    
    # Timing preferences
    quiet_hours_start = models.TimeField(blank=True, null=True, help_text="Start of quiet hours (no notifications)")
    quiet_hours_end = models.TimeField(blank=True, null=True, help_text="End of quiet hours")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'notifications_preference'
        verbose_name = 'Notification Preference'
        verbose_name_plural = 'Notification Preferences'
    
    def __str__(self):
        return f"Preferences for {self.user.username}"
    
    def should_receive_notification(self, notification_type, delivery_method):
        """Check if user should receive specific notification type via delivery method"""
        # Check global preferences
        if delivery_method == 'email' and not self.receive_email:
            return False
        elif delivery_method == 'sms' and not self.receive_sms:
            return False
        elif delivery_method == 'push' and not self.receive_push:
            return False
        
        # Check specific notification type preferences
        type_mapping = {
            'order_status': self.order_updates,
            'order_ready': self.order_updates,
            'order_cancelled': self.order_updates,
            'payment_success': self.payment_updates,
            'payment_failed': self.payment_updates,
            'menu_update': self.menu_updates,
            'promotion': self.promotions,
            'system_announcement': self.system_announcements,
        }
        
        return type_mapping.get(notification_type, True)
    
    def is_in_quiet_hours(self):
        """Check if current time is within user's quiet hours"""
        if not (self.quiet_hours_start and self.quiet_hours_end):
            return False
        
        now = timezone.now().time()
        return self.quiet_hours_start <= now <= self.quiet_hours_end