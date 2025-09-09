from django.db import models
from django.core.validators import MinValueValidator, RegexValidator
from django.conf import settings
from django.utils import timezone
import uuid
import json

class Payment(models.Model):
    """Main payment model"""
    
    PAYMENT_METHOD_CHOICES = [
        ('mtn_momo', 'MTN Mobile Money'),
        ('orange_money', 'Orange Money'),
        ('wallet', 'Wallet Balance'),
        ('cash', 'Cash Payment'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    ]
    
    TRANSACTION_TYPE_CHOICES = [
        ('order_payment', 'Order Payment'),
        ('wallet_topup', 'Wallet Top-up'),
        ('refund', 'Refund'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment_reference = models.CharField(max_length=50, unique=True, db_index=True)
    
    # Related objects
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payments'
    )
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.CASCADE,
        related_name='payments',
        blank=True,
        null=True
    )
    
    # Payment details
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES, default='order_payment')
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0.01)]
    )
    currency = models.CharField(max_length=3, default='XAF')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Mobile Money specific fields
    phone_regex = RegexValidator(
        regex=r'^\+?237?[2368]\d{7,8}$',
        message="Phone number must be in Cameroon format"
    )
    phone_number = models.CharField(
        validators=[phone_regex],
        max_length=17,
        blank=True,
        help_text="Phone number for mobile money payment"
    )
    
    # Transaction details
    transaction_id = models.CharField(max_length=100, blank=True, db_index=True)
    external_reference = models.CharField(max_length=100, blank=True)
    provider_response = models.JSONField(default=dict, blank=True)
    
    # Fees and charges
    transaction_fee = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        default=0.00
    )
    net_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    
    # Metadata
    description = models.TextField(blank=True)
    failure_reason = models.TextField(blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'payments_payment'
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['payment_method']),
            models.Index(fields=['user', '-created_at']),
        ]
    
    def __str__(self):
        return f"Payment {self.payment_reference} - {self.amount} {self.currency}"
    
    @property
    def is_successful(self):
        return self.status == 'completed'
    
    @property
    def is_pending(self):
        return self.status in ['pending', 'processing']
    
    @property
    def can_retry(self):
        return self.status == 'failed' and self.retry_count < 3
    
    def mark_as_processing(self):
        self.status = 'processing'
        self.processed_at = timezone.now()
        self.save(update_fields=['status', 'processed_at'])
    
    def mark_as_completed(self, transaction_id=None):
        self.status = 'completed'
        self.completed_at = timezone.now()
        if transaction_id:
            self.transaction_id = transaction_id
        self.save(update_fields=['status', 'completed_at', 'transaction_id'])
    
    def mark_as_failed(self, reason=None):
        self.status = 'failed'
        self.retry_count += 1
        if reason:
            self.failure_reason = reason
        self.save(update_fields=['status', 'retry_count', 'failure_reason'])
    
    def calculate_net_amount(self):
        """Calculate net amount after transaction fees"""
        # MTN Mobile Money: 1% fee, min 100 XAF, max 500 XAF
        # Orange Money: 0.5% fee, min 50 XAF, max 300 XAF
        if self.payment_method == 'mtn_momo':
            fee = max(100, min(500, self.amount * 0.01))
        elif self.payment_method == 'orange_money':
            fee = max(50, min(300, self.amount * 0.005))
        else:
            fee = 0
        
        self.transaction_fee = fee
        self.net_amount = self.amount - fee
        return self.net_amount


class WalletTransaction(models.Model):
    """Track all wallet-related transactions"""
    
    TRANSACTION_TYPE_CHOICES = [
        ('credit', 'Credit'),
        ('debit', 'Debit'),
    ]
    
    SOURCE_CHOICES = [
        ('topup', 'Wallet Top-up'),
        ('order_payment', 'Order Payment'),
        ('refund', 'Refund'),
        ('bonus', 'Bonus Credit'),
        ('admin_adjustment', 'Admin Adjustment'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='wallet_transactions'
    )
    
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPE_CHOICES)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Balances
    balance_before = models.DecimalField(max_digits=10, decimal_places=2)
    balance_after = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Related objects
    payment = models.ForeignKey(
        Payment,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='wallet_transactions'
    )
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='wallet_transactions'
    )
    
    description = models.CharField(max_length=255)
    reference = models.CharField(max_length=50, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='wallet_adjustments'
    )
    
    class Meta:
        db_table = 'payments_wallet_transaction'
        verbose_name = 'Wallet Transaction'
        verbose_name_plural = 'Wallet Transactions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.transaction_type} {self.amount} XAF"


class PaymentProvider(models.Model):
    """Configuration for payment providers"""
    
    PROVIDER_CHOICES = [
        ('mtn_momo', 'MTN Mobile Money'),
        ('orange_money', 'Orange Money'),
    ]
    
    name = models.CharField(max_length=20, choices=PROVIDER_CHOICES, unique=True)
    display_name = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)
    
    # API Configuration (encrypted in production)
    api_endpoint = models.URLField()
    api_key = models.CharField(max_length=255, blank=True)
    secret_key = models.CharField(max_length=255, blank=True)
    merchant_id = models.CharField(max_length=100, blank=True)
    
    # Fee configuration
    fee_percentage = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    minimum_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    maximum_fee = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    
    # Transaction limits
    min_amount = models.DecimalField(max_digits=10, decimal_places=2, default=100)
    max_amount = models.DecimalField(max_digits=10, decimal_places=2, default=500000)
    daily_limit = models.DecimalField(max_digits=12, decimal_places=2, default=2000000)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'payments_provider'
        verbose_name = 'Payment Provider'
        verbose_name_plural = 'Payment Providers'
    
    def __str__(self):
        return self.display_name
    
    def calculate_fee(self, amount):
        """Calculate transaction fee for given amount"""
        fee = amount * (self.fee_percentage / 100)
        return max(self.minimum_fee, min(self.maximum_fee, fee))


class PaymentWebhook(models.Model):
    """Store webhook data from payment providers"""
    
    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name='webhooks'
    )
    provider = models.CharField(max_length=20)
    webhook_data = models.JSONField()
    processed = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        db_table = 'payments_webhook'
        verbose_name = 'Payment Webhook'
        verbose_name_plural = 'Payment Webhooks'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Webhook for {self.payment.payment_reference}"