from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal


class User(AbstractUser):
    """Extended user model with role-based access control"""
    ROLE_CHOICES = [
        ('customer', 'Customer'),
        ('producer', 'Producer'),
        ('community_group', 'Community Group'),
        ('restaurant', 'Restaurant'),
        ('admin', 'Admin'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='customer')
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    postcode = models.CharField(max_length=10, blank=True)

    def is_producer(self):
        return self.role == 'producer'

    def is_customer(self):
        return self.role in ('customer', 'community_group', 'restaurant')

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
    
    def save(self, *args, **kwargs):
        # Ensure Django superusers always behave like your app "admin"
        if self.is_superuser:
            self.role = 'admin'
            self.is_staff = True
        super().save(*args, **kwargs)


class ProducerProfile(models.Model):
    """Extended profile for producer accounts"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='producer_profile')
    business_name = models.CharField(max_length=200)
    contact_name = models.CharField(max_length=100)
    farm_address = models.TextField()
    farm_postcode = models.CharField(max_length=10)
    description = models.TextField(blank=True)
    lead_time_hours = models.PositiveIntegerField(
        default=48,
        help_text="Minimum hours needed to prepare orders"
    )

    def __str__(self):
        return self.business_name


class CustomerProfile(models.Model):
    """Extended profile for customer accounts"""
    CUSTOMER_TYPE_CHOICES = [
        ('individual', 'Individual'),
        ('family', 'Family'),
        ('community_group', 'Community Group'),
        ('restaurant', 'Restaurant/Cafe'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='customer_profile')
    customer_type = models.CharField(max_length=20, choices=CUSTOMER_TYPE_CHOICES, default='individual')
    organisation_name = models.CharField(max_length=200, blank=True)
    delivery_address = models.TextField()
    delivery_postcode = models.CharField(max_length=10)

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.get_customer_type_display()})"


class Category(models.Model):
    """Product categories"""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = 'categories'
        ordering = ['name']

    def __str__(self):
        return self.name


# UK 14 major allergens (Food Information Regulations 2014)
ALLERGEN_CHOICES = [
    ('celery', 'Celery'),
    ('gluten', 'Gluten (Wheat/Rye/Barley/Oats)'),
    ('crustaceans', 'Crustaceans'),
    ('eggs', 'Eggs'),
    ('fish', 'Fish'),
    ('lupin', 'Lupin'),
    ('milk', 'Milk'),
    ('molluscs', 'Molluscs'),
    ('mustard', 'Mustard'),
    ('nuts', 'Tree Nuts'),
    ('peanuts', 'Peanuts'),
    ('sesame', 'Sesame'),
    ('soya', 'Soya'),
    ('sulphites', 'Sulphur Dioxide/Sulphites'),
]


class Product(models.Model):
    """Products listed by producers on the marketplace"""
    AVAILABILITY_CHOICES = [
        ('available', 'Available'),
        ('in_season', 'In Season'),
        ('out_of_season', 'Out of Season'),
        ('unavailable', 'Unavailable'),
    ]
    UNIT_CHOICES = [
        ('kg', 'Kilogram (kg)'),
        ('g', 'Gram (g)'),
        ('litre', 'Litre'),
        ('dozen', 'Dozen'),
        ('each', 'Each'),
        ('bunch', 'Bunch'),
        ('pack', 'Pack'),
    ]

    producer = models.ForeignKey(ProducerProfile, on_delete=models.CASCADE, related_name='products')
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='products')
    name = models.CharField(max_length=200)
    description = models.TextField()
    price = models.DecimalField(
        max_digits=8, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    unit = models.CharField(max_length=20, choices=UNIT_CHOICES, default='each')
    stock_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    low_stock_threshold = models.DecimalField(max_digits=10, decimal_places=2, default=10)
    availability = models.CharField(max_length=20, choices=AVAILABILITY_CHOICES, default='available')
    is_organic = models.BooleanField(default=False)
    harvest_date = models.DateField(null=True, blank=True)
    best_before_date = models.DateField(null=True, blank=True)
    season_start_month = models.PositiveIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    season_end_month = models.PositiveIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    image = models.ImageField(upload_to='products/', null=True, blank=True)
    is_surplus = models.BooleanField(default=False)
    surplus_discount_percent = models.PositiveIntegerField(
        default=0,
        validators=[MaxValueValidator(100)]
    )
    surplus_expiry = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def discounted_price(self):
        if self.is_surplus and self.surplus_discount_percent > 0:
            discount = self.price * Decimal(self.surplus_discount_percent) / 100
            return round(self.price - discount, 2)
        return self.price

    @property
    def is_available(self):
        return self.availability in ('available', 'in_season') and self.stock_quantity > 0

    def __str__(self):
        return f"{self.name} — {self.producer.business_name}"

    class Meta:
        ordering = ['name']


class ProductAllergen(models.Model):
    """Allergens associated with a product (all 14 UK major allergens supported)"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='product_allergens')
    allergen = models.CharField(max_length=20, choices=ALLERGEN_CHOICES)

    class Meta:
        unique_together = ('product', 'allergen')

    def __str__(self):
        return f"{self.product.name} — {self.get_allergen_display()}"


class Order(models.Model):
    """A customer order (can span multiple producers)"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('ready', 'Ready for Collection/Delivery'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]

    COMMISSION_RATE = Decimal('0.05')  # 5% network commission

    customer = models.ForeignKey(User, on_delete=models.PROTECT, related_name='orders')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    delivery_address = models.TextField()
    delivery_postcode = models.CharField(max_length=10)
    delivery_date = models.DateField()
    special_instructions = models.TextField(blank=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_reference = models.CharField(max_length=100, blank=True)
    payment_status = models.CharField(max_length=20, default='pending')
    payment_status = models.CharField(max_length=20, default='pending')
    recurring_order = models.ForeignKey(         
        'RecurringOrder',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generated_orders',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def calculate_commission(self):
        self.commission_amount = round(self.total_amount * self.COMMISSION_RATE, 2)
        return self.commission_amount

    def sync_status_from_items(self, save=True):
        """
        Aggregate Order.status from OrderItem.producer_status.
        Rules:
          - If all items are cancelled -> cancelled
          - Otherwise, ignore cancelled items for progress
          - delivered only if ALL active items delivered
          - ready only if ALL active items are at least ready
          - confirmed only if ALL active items are at least confirmed
          - else pending
        """
        rank = {
            'pending': 0,
            'confirmed': 1,
            'ready': 2,
            'delivered': 3,
        }

        qs = self.items.all()
        if not qs.exists():
            new_status = 'pending'
        else:
            active = qs.exclude(producer_status='cancelled')

            # everything cancelled
            if active.count() == 0:
                new_status = 'cancelled'
            else:
                min_rank = min(rank.get(i.producer_status, 0) for i in active)

                if min_rank >= rank['delivered']:
                    new_status = 'delivered'
                elif min_rank >= rank['ready']:
                    new_status = 'ready'
                elif min_rank >= rank['confirmed']:
                    new_status = 'confirmed'
                else:
                    new_status = 'pending'

        changed = (self.status != new_status)
        old_status = self.status
        self.status = new_status

        if changed and save:
            self.save(update_fields=['status', 'updated_at'])

        return changed, old_status, new_status

    def __str__(self):
        return f"Order #{self.pk} — {self.customer.username}"

    class Meta:
        ordering = ['-created_at']


class OrderItem(models.Model):
    """A single product line within an order"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    producer = models.ForeignKey(ProducerProfile, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_price = models.DecimalField(max_digits=8, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    # Each producer manages their own portion's status
    producer_status = models.CharField(max_length=20, choices=Order.STATUS_CHOICES, default='pending')
    producer_notes = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        self.subtotal = round(Decimal(str(self.quantity)) * self.unit_price, 2)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name} ×{self.quantity} (Order #{self.order.pk})"


class Cart(models.Model):
    """Shopping cart — one per customer"""
    customer = models.OneToOneField(User, on_delete=models.CASCADE, related_name='cart')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def total(self):
        return round(sum(item.subtotal for item in self.cart_items.all()), 2)

    @property
    def item_count(self):
        return self.cart_items.count()

    def __str__(self):
        return f"Cart — {self.customer.username}"


class CartItem(models.Model):
    """A product in a shopping cart"""
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='cart_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )

    @property
    def subtotal(self):
        return round(Decimal(str(self.quantity)) * self.product.discounted_price, 2)

    class Meta:
        unique_together = ('cart', 'product')

    def __str__(self):
        return f"{self.product.name} ×{self.quantity}"


class PaymentSettlement(models.Model):
    """Weekly payment settlements to producers (95% of order value)"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    producer = models.ForeignKey(ProducerProfile, on_delete=models.PROTECT, related_name='settlements')
    week_start = models.DateField()
    week_end = models.DateField()
    gross_amount = models.DecimalField(max_digits=10, decimal_places=2)
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2)
    net_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_reference = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Settlement {self.producer.business_name} ({self.week_start} – {self.week_end})"


class OrderStatusHistory(models.Model):
    """Full audit trail of all order status changes"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_history')
    order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE, null=True, blank=True)
    old_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    notes = models.TextField(blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'order status histories'
        ordering = ['-changed_at']

    def __str__(self):
        return f"Order #{self.order.pk}: {self.old_status} → {self.new_status}"


class RecurringOrder(models.Model):
    """Recurring weekly order template for restaurant accounts"""
    DAY_CHOICES = [
        ('monday',    'Monday'),
        ('tuesday',   'Tuesday'),
        ('wednesday', 'Wednesday'),
        ('thursday',  'Thursday'),
        ('friday',    'Friday'),
        ('saturday',  'Saturday'),
        ('sunday',    'Sunday'),
    ]

    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recurring_orders')
    name = models.CharField(max_length=200, help_text='e.g. "Weekly Kitchen Basics"')
    order_day = models.CharField(
        max_length=10, choices=DAY_CHOICES, default='monday',
        help_text='Day the order is placed each week'
    )
    delivery_day = models.CharField(
        max_length=10, choices=DAY_CHOICES, default='wednesday',
        help_text='Day delivery is expected each week'
    )
    delivery_address = models.TextField()
    delivery_postcode = models.CharField(max_length=10)
    special_instructions = models.TextField(blank=True)
    is_paused = models.BooleanField(default=False)
    next_order_date = models.DateField(
        null=True, blank=True,
        help_text='Date the next Order will be generated'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.customer.username})"

    @property
    def estimated_weekly_total(self):
        return round(sum(
            item.product.discounted_price * item.quantity
            for item in self.template_items.select_related('product').all()
        ), 2)

    def compute_next_order_date(self):
        from datetime import date, timedelta
        day_map = {
            'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
            'friday': 4, 'saturday': 5, 'sunday': 6,
        }
        target = day_map[self.order_day]
        today = date.today()
        days_ahead = (target - today.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        return today + timedelta(days=days_ahead)

    class Meta:
        ordering = ['name']


class RecurringOrderItem(models.Model):
    """One product line inside a RecurringOrder template"""
    recurring_order = models.ForeignKey(
        RecurringOrder, on_delete=models.CASCADE,
        related_name='template_items'
    )
    product = models.ForeignKey('Product', on_delete=models.CASCADE)
    quantity = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    notes = models.CharField(max_length=300, blank=True)

    class Meta:
        unique_together = ('recurring_order', 'product')

    def __str__(self):
        return f"{self.product.name} x{self.quantity} — {self.recurring_order.name}"
    


class Review(models.Model):
    """
    TC-024: Customer product reviews and ratings.
    - Only customers who have purchased and received the product can review
    - One review per customer per product
    - Ratings 1-5 stars
    - Optional anonymous display
    """
    product     = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    customer    = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    order_item  = models.ForeignKey(OrderItem, on_delete=models.CASCADE, related_name='reviews')
    rating      = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    title       = models.CharField(max_length=200)
    body        = models.TextField()
    is_anonymous = models.BooleanField(default=False)
    is_flagged   = models.BooleanField(default=False)   # moderation flag
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('product', 'customer')   # one review per customer per product
        ordering = ['-created_at']

    def __str__(self):
        name = "Anonymous" if self.is_anonymous else self.customer.get_full_name() or self.customer.username
        return f"{self.product.name} — {self.rating}★ by {name}"

    @property
    def display_name(self):
        if self.is_anonymous:
            return "Anonymous"
        return self.customer.get_full_name() or self.customer.username
