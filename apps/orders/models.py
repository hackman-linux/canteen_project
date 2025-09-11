
import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


def generate_order_number():
    """Simple readable order number generator (falls back to uuid4 hex)."""
    return uuid.uuid4().hex[:12].upper()


class Order(models.Model):
    """Main order placed by an employee."""

    STATUS_PENDING = "PENDING"
    STATUS_VALIDATED = "VALIDATED"
    STATUS_CANCELLED = "CANCELLED"
    STATUS_PAID = "PAID"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_VALIDATED, "Validated"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_PAID, "Paid"),
    ]

    PAYMENT_WALLET = "wallet"
    PAYMENT_MTN = "mtn_momo"
    PAYMENT_ORANGE = "orange_money"

    PAYMENT_METHOD_CHOICES = [
        (PAYMENT_WALLET, "Wallet"),
        (PAYMENT_MTN, "MTN Mobile Money"),
        (PAYMENT_ORANGE, "Orange Money"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(max_length=32, unique=True, default=generate_order_number)

    # Who placed the order
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="orders",
    )

    # Contact info (captured at checkout)
    full_name = models.CharField(max_length=255, blank=False, null=False, default="Souleman G")
    email = models.EmailField(max_length=255, blank=False, null=False, default="ndjodongouhs@gmail.com")
    phone_number = models.CharField(max_length=50, blank=False, null=False, default='+237 688 582 648')
    office_number = models.CharField(max_length=50, blank=True)

    # Order summary fields (stored for auditing — also recalculated via calculate_totals())
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    service_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    # Optional notes
    special_instructions = models.TextField(blank=True)

    # Status & payment
    actual_prep_time = models.DurationField(null=True, blank=True, help_text="Time taken to prepare the order")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    payment_method = models.CharField(max_length=30, choices=PAYMENT_METHOD_CHOICES, blank=True, null=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    validated_at = models.DateTimeField(blank=True, null=True)
    paid_at = models.DateTimeField(blank=True, null=True)
    cancelled_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "orders_order"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["employee", "created_at"]),
            models.Index(fields=["status"]),
            models.Index(fields=["order_number"]),
        ]

    def __str__(self):
        return f"{self.order_number} — {self.get_status_display()}"

    def calculate_totals(self, save=False):
        """Recalculate subtotal / tax / total from items. Call after creating items."""
        subtotal = Decimal("0.00")
        for item in self.items.all():
            # item.unit_price should be stored on item.save()
            subtotal += (item.unit_price or Decimal("0.00")) * item.quantity

        # Basic tax/service calculation placeholders — adjust to your rules
        service_fee = (subtotal * Decimal("0.00"))  # set to non-zero if needed
        tax_amount = (subtotal * Decimal("0.00"))  # set VAT / tax logic here
        total = subtotal + service_fee + tax_amount

        self.subtotal = subtotal.quantize(Decimal("0.01"))
        self.service_fee = service_fee.quantize(Decimal("0.01"))
        self.tax_amount = tax_amount.quantize(Decimal("0.01"))
        self.total_amount = total.quantize(Decimal("0.01"))

        if save:
            self.save()

        return {
            "subtotal": self.subtotal,
            "service_fee": self.service_fee,
            "tax_amount": self.tax_amount,
            "total_amount": self.total_amount,
        }


class OrderItem(models.Model):
    """Individual line item in an order."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    menu_item = models.ForeignKey("menu.MenuItem", on_delete=models.PROTECT, related_name="order_items")
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        db_table = "orders_orderitem"
        ordering = ["-id"]

    def __str__(self):
        return f"{self.menu_item.name} x {self.quantity}"

    @property
    def total(self):
        return (self.unit_price or Decimal("0.00")) * self.quantity

    def save(self, *args, **kwargs):
        # Snapshot the menu item price at ordering time
        if not self.unit_price and hasattr(self.menu_item, "price"):
            self.unit_price = self.menu_item.price
        super().save(*args, **kwargs)


class OrderQueue(models.Model):
    """Optional queue model for kitchen / canteen admins to reorder processing."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="queue_entry")
    queue_position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "orders_orderqueue"
        ordering = ["queue_position", "-created_at"]
        indexes = [models.Index(fields=["queue_position", "created_at"])]

    def __str__(self):
        return f"Queue #{self.queue_position} — {self.order.order_number}"


class OrderHistory(models.Model):
    """Track order status changes for audit / timeline."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="history")
    status_from = models.CharField(max_length=50, blank=True)
    status_to = models.CharField(max_length=50)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="order_changes")
    notes = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "orders_orderhistory"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["changed_by", "timestamp"]),
        ]

    def __str__(self):
        return f"{self.order.order_number}: {self.status_from} -> {self.status_to} at {self.timestamp}"


class ReorderItem(models.Model):
    """Simple model to keep fast-reorder entries for a user."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reorder_items")
    menu_item = models.ForeignKey("menu.MenuItem", on_delete=models.CASCADE, related_name="reorder_items")
    quantity = models.PositiveIntegerField(default=1)
    last_ordered = models.DateTimeField(auto_now=True)
    order_count = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "orders_reorderitem"
        unique_together = [("user", "menu_item")]
        ordering = ["-last_ordered"]

    def __str__(self):
        return f"{self.user} — {self.menu_item.name} ({self.quantity})"

    def increment_order_count(self):
        self.order_count += 1
        self.last_ordered = timezone.now()
        self.save()
