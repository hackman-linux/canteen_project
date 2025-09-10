from django.db import models
from django.conf import settings
from django.utils import timezone


# ------------------------------------
# Shared constants
# ------------------------------------
NOTIFICATION_TYPE_CHOICES = [
    ("order_status", "Order Status Update"),
    ("order_ready", "Order Ready"),
    ("order_cancelled", "Order Cancelled"),
    ("payment_success", "Payment Successful"),
    ("payment_failed", "Payment Failed"),
    ("menu_update", "Menu Update"),
    ("system_announcement", "System Announcement"),
    ("low_stock", "Low Stock Alert"),
    ("wallet_topup", "Wallet Top-up"),
    ("promotion", "Promotion/Offer"),
    ("maintenance", "System Maintenance"),
]


# ------------------------------------
# Models
# ------------------------------------
class Notification(models.Model):
    TYPE_CHOICES = NOTIFICATION_TYPE_CHOICES

    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications"
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def mark_as_read(self):
        self.is_read = True
        self.save(update_fields=["is_read"])

    def __str__(self):
        return f"{self.title} - {self.user}"

    class Meta:
        ordering = ["-created_at"]


class NotificationTemplate(models.Model):
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(
        max_length=20,
        choices=NOTIFICATION_TYPE_CHOICES
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Template: {self.title} ({self.notification_type})"

    class Meta:
        verbose_name = "Notification Template"
        verbose_name_plural = "Notification Templates"
        ordering = ["-created_at"]
