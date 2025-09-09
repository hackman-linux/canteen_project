from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings
from django.utils import timezone
import uuid

class MenuCategory(models.Model):
    """Menu categories like Starters, Main Course, Beverages, etc."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(
        max_length=50, 
        default='bi-card-list',
        help_text="Bootstrap icon class name"
    )
    color = models.CharField(
        max_length=20,
        default='primary',
        help_text="Bootstrap color class"
    )
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_categories'
    )
    
    class Meta:
        db_table = 'menu_category'
        verbose_name = 'Menu Category'
        verbose_name_plural = 'Menu Categories'
        ordering = ['display_order', 'name']
        indexes = [
            models.Index(fields=['is_active']),
            models.Index(fields=['display_order']),
        ]
    
    def __str__(self):
        return self.name
    
    def get_active_items(self):
        """Get active menu items in this category"""
        return self.menu_items.filter(is_available=True)
    
    def get_items_count(self):
        """Get total count of items in this category"""
        return self.menu_items.count()


class MenuItem(models.Model):
    """Individual menu items"""
    
    SPICE_LEVEL_CHOICES = [
        ('none', 'Not Spicy'),
        ('mild', 'Mild'),
        ('medium', 'Medium'),
        ('hot', 'Hot'),
        ('very_hot', 'Very Hot'),
    ]
    
    DIETARY_CHOICES = [
        ('vegetarian', 'Vegetarian'),
        ('vegan', 'Vegan'),
        ('gluten_free', 'Gluten Free'),
        ('dairy_free', 'Dairy Free'),
        ('halal', 'Halal'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.ForeignKey(
        MenuCategory, 
        on_delete=models.CASCADE, 
        related_name='menu_items'
    )
    
    # Basic information
    name = models.CharField(max_length=200)
    description = models.TextField()
    price = models.DecimalField(
        max_digits=8, 
        decimal_places=2,
        validators=[MinValueValidator(0.01)]
    )
    image = models.ImageField(
        upload_to='menu_items/', 
        blank=True, 
        null=True
    )
    
    # Nutritional and dietary info
    calories = models.PositiveIntegerField(blank=True, null=True)
    spice_level = models.CharField(
        max_length=20, 
        choices=SPICE_LEVEL_CHOICES, 
        default='none'
    )
    dietary_tags = models.JSONField(
        default=list, 
        blank=True,
        help_text="List of dietary tags"
    )
    allergens = models.TextField(
        blank=True,
        help_text="List allergens separated by commas"
    )
    
    # Availability and inventory
    is_available = models.BooleanField(default=True)
    daily_limit = models.PositiveIntegerField(
        default=100,
        help_text="Maximum orders per day, 0 for unlimited"
    )
    current_stock = models.PositiveIntegerField(default=100)
    low_stock_threshold = models.PositiveIntegerField(default=10)
    
    # Preparation details
    preparation_time = models.PositiveIntegerField(
        default=15,
        help_text="Preparation time in minutes"
    )
    cooking_instructions = models.TextField(blank=True)
    
    # Popularity and ratings
    total_orders = models.PositiveIntegerField(default=0)
    average_rating = models.DecimalField(
        max_digits=3, 
        decimal_places=2, 
        default=0.00,
        validators=[MinValueValidator(0.00), MaxValueValidator(5.00)]
    )
    total_reviews = models.PositiveIntegerField(default=0)
    
    # Timestamps and tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_menu_items'
    )
    
    # Special flags
    is_featured = models.BooleanField(default=False)
    is_special = models.BooleanField(default=False)
    special_price = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        blank=True, 
        null=True
    )
    special_until = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        db_table = 'menu_item'
        verbose_name = 'Menu Item'
        verbose_name_plural = 'Menu Items'
        ordering = ['-is_featured', '-is_special', 'category__display_order', 'name']
        indexes = [
            models.Index(fields=['is_available']),
            models.Index(fields=['is_featured']),
            models.Index(fields=['is_special']),
            models.Index(fields=['category', 'is_available']),
            models.Index(fields=['total_orders']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.category.name}"
    
    def get_display_price(self):
        """Get the display price (special price if active, otherwise regular price)"""
        if self.is_special_active():
            return self.special_price or self.price
        return self.price
    
    def is_special_active(self):
        """Check if special offer is currently active"""
        if not self.is_special or not self.special_until:
            return False
        return timezone.now() <= self.special_until
    
    def get_discount_percentage(self):
        """Calculate discount percentage if special offer is active"""
        if self.is_special_active() and self.special_price:
            discount = ((self.price - self.special_price) / self.price) * 100
            return round(discount, 0)
        return 0
    
    def is_in_stock(self):
        """Check if item is in stock"""
        if self.daily_limit == 0:  # Unlimited
            return self.current_stock > 0
        return self.current_stock > 0 and self.get_daily_orders_count() < self.daily_limit
    
    def is_low_stock(self):
        """Check if item is low in stock"""
        return self.current_stock <= self.low_stock_threshold
    
    def get_daily_orders_count(self):
        """Get number of orders for this item today"""
        from apps.orders.models import OrderItem
        today = timezone.now().date()
        return OrderItem.objects.filter(
            menu_item=self,
            order__created_at__date=today,
            order__status__in=['confirmed', 'preparing', 'ready', 'completed']
        ).aggregate(
            total=models.Sum('quantity')
        )['total'] or 0
    
    def update_stock(self, quantity_used):
        """Update stock after an order"""
        if self.current_stock >= quantity_used:
            self.current_stock -= quantity_used
            self.save(update_fields=['current_stock'])
            return True
        return False
    
    def restock(self, quantity):
        """Add stock to the item"""
        self.current_stock += quantity
        self.save(update_fields=['current_stock'])
    
    def increment_orders(self, quantity=1):
        """Increment total orders count"""
        self.total_orders += quantity
        self.save(update_fields=['total_orders'])
    
    def update_rating(self, new_rating):
        """Update average rating with new rating"""
        total_rating = self.average_rating * self.total_reviews
        self.total_reviews += 1
        self.average_rating = (total_rating + new_rating) / self.total_reviews
        self.save(update_fields=['average_rating', 'total_reviews'])
    
    def get_rating_stars(self):
        """Get star rating display"""
        full_stars = int(self.average_rating)
        half_star = 1 if self.average_rating - full_stars >= 0.5 else 0
        empty_stars = 5 - full_stars - half_star
        
        return {
            'full': full_stars,
            'half': half_star,
            'empty': empty_stars,
            'rating': self.average_rating
        }
    
    def get_dietary_tags_display(self):
        """Get formatted dietary tags for display"""
        tag_labels = {
            'vegetarian': '🥗 Vegetarian',
            'vegan': '🌱 Vegan',
            'gluten_free': '🚫 Gluten Free',
            'dairy_free': '🥛 Dairy Free',
            'halal': '☪️ Halal',
        }
        return [tag_labels.get(tag, tag.title()) for tag in self.dietary_tags]
    
    def get_spice_level_display(self):
        """Get spice level with emoji"""
        spice_emojis = {
            'none': '',
            'mild': '🌶️',
            'medium': '🌶️🌶️',
            'hot': '🌶️🌶️🌶️',
            'very_hot': '🌶️🌶️🌶️🌶️'
        }
        return spice_emojis.get(self.spice_level, '')


class MenuItemReview(models.Model):
    """Customer reviews for menu items"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    menu_item = models.ForeignKey(
        MenuItem, 
        on_delete=models.CASCADE, 
        related_name='reviews'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='menu_reviews'
    )
    
    rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(blank=True)
    
    # Review metadata
    is_verified_purchase = models.BooleanField(default=False)
    helpful_count = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'menu_item_review'
        verbose_name = 'Menu Item Review'
        verbose_name_plural = 'Menu Item Reviews'
        unique_together = ['menu_item', 'user']
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['menu_item', 'rating']),
            models.Index(fields=['is_verified_purchase']),
        ]
    
    def __str__(self):
        return f"{self.user.get_short_name()} - {self.menu_item.name} ({self.rating}⭐)"


class DailyMenu(models.Model):
    """Daily menu configuration"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    date = models.DateField(unique=True)
    menu_items = models.ManyToManyField(
        MenuItem, 
        through='DailyMenuItems',
        related_name='daily_menus'
    )
    
    # Special information
    special_message = models.TextField(blank=True)
    is_published = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_daily_menus'
    )
    
    class Meta:
        db_table = 'daily_menu'
        verbose_name = 'Daily Menu'
        verbose_name_plural = 'Daily Menus'
        ordering = ['-date']
        indexes = [
            models.Index(fields=['date']),
            models.Index(fields=['is_published']),
        ]
    
    def __str__(self):
        return f"Menu for {self.date}"
    
    @classmethod
    def get_today_menu(cls):
        """Get today's published menu"""
        today = timezone.now().date()
        try:
            return cls.objects.get(date=today, is_published=True)
        except cls.DoesNotExist:
            return None
    
    def get_categories_with_items(self):
        """Get menu categories with their items for this daily menu"""
        from django.db.models import Prefetch
        
        return MenuCategory.objects.filter(
            menu_items__daily_menu_items__daily_menu=self
        ).prefetch_related(
            Prefetch(
                'menu_items',
                queryset=MenuItem.objects.filter(
                    daily_menu_items__daily_menu=self
                ).select_related('category')
            )
        ).distinct()


class DailyMenuItems(models.Model):
    """Through model for DailyMenu and MenuItem relationship"""
    
    daily_menu = models.ForeignKey(
        DailyMenu, 
        on_delete=models.CASCADE,
        related_name='daily_menu_items'
    )
    menu_item = models.ForeignKey(
        MenuItem, 
        on_delete=models.CASCADE,
        related_name='daily_menu_items'
    )
    
    # Daily specific overrides
    daily_price = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        blank=True, 
        null=True,
        help_text="Override price for this day"
    )
    daily_stock = models.PositiveIntegerField(
        blank=True, 
        null=True,
        help_text="Override stock for this day"
    )
    is_featured_today = models.BooleanField(default=False)
    display_order = models.PositiveIntegerField(default=0)
    
    class Meta:
        db_table = 'daily_menu_items'
        unique_together = ['daily_menu', 'menu_item']
        ordering = ['display_order', 'menu_item__name']
    
    def get_effective_price(self):
        """Get effective price for this daily menu item"""
        return self.daily_price or self.menu_item.get_display_price()
    
    def get_effective_stock(self):
        """Get effective stock for this daily menu item"""
        return self.daily_stock or self.menu_item.current_stock


class MenuItemFavorite(models.Model):
    """User favorites for menu items"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='favorite_items'
    )
    menu_item = models.ForeignKey(
        MenuItem,
        on_delete=models.CASCADE,
        related_name='favorited_by'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'menu_item_favorite'
        unique_together = ['user', 'menu_item']
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user']),
        ]
    
    def __str__(self):
        return f"{self.user.get_short_name()} ❤️ {self.menu_item.name}"


class MenuItemIngredient(models.Model):
    """Ingredients for menu items (for dietary and allergen info)"""
    
    name = models.CharField(max_length=100, unique=True)
    is_allergen = models.BooleanField(default=False)
    dietary_restrictions = models.JSONField(
        default=list,
        help_text="List of dietary restrictions this ingredient affects"
    )
    
    class Meta:
        db_table = 'menu_item_ingredient'
        verbose_name = 'Ingredient'
        verbose_name_plural = 'Ingredients'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class MenuItemIngredientRelation(models.Model):
    """Relationship between menu items and their ingredients"""
    
    menu_item = models.ForeignKey(
        MenuItem,
        on_delete=models.CASCADE,
        related_name='ingredient_relations'
    )
    ingredient = models.ForeignKey(
        MenuItemIngredient,
        on_delete=models.CASCADE,
        related_name='menu_item_relations'
    )
    quantity = models.CharField(max_length=50, blank=True)  # e.g., "2 cups", "100g"
    is_optional = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'menu_item_ingredient_relation'
        unique_together = ['menu_item', 'ingredient']
    
    def __str__(self):
        return f"{self.menu_item.name} - {self.ingredient.name}"