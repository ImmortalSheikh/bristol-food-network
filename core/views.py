from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Avg
from django.core.exceptions import PermissionDenied
from django.core.cache import cache
from decimal import Decimal
from datetime import date, timedelta, datetime
import requests
import math

from .models import (
    User, Product, Category, Cart, CartItem,
    Order, OrderItem, ProducerProfile, CustomerProfile, OrderStatusHistory,
    RecurringOrder, RecurringOrderItem, Review,
    PaymentSettlement, Recipe, FarmStory, FavouriteRecipe
)
from .forms import (
    ProducerRegistrationForm, CustomerRegistrationForm,
    LoginForm, ProductForm, CartItemForm, RecurringOrderForm,
    RecipeForm, FarmStoryForm
)


# ─────────────────────────────────────────────────────────────
# FOOD MILES HELPER (TC-013)
# ─────────────────────────────────────────────────────────────

def _get_postcode_coords(postcode):
    """Fetch lat/lng for a UK postcode from postcodes.io. Results cached in Redis for 24h."""
    postcode_clean = postcode.strip().replace(' ', '').upper()
    cache_key = f"postcode_{postcode_clean}"
    cached = cache.get(cache_key)
    if cached:
        return cached
    try:
        response = requests.get(
            f"https://api.postcodes.io/postcodes/{postcode_clean}",
            timeout=2
        )
        if response.status_code == 200:
            data = response.json()
            coords = (data['result']['latitude'], data['result']['longitude'])
            cache.set(cache_key, coords, timeout=86400)  # cache 24 hours
            return coords
    except Exception:
        pass
    return None, None


def _haversine_miles(lat1, lon1, lat2, lon2):
    """Calculate straight-line distance in miles between two lat/lng points."""
    R = 3958.8
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return round(R * c, 1)


def _calculate_food_miles(customer_postcode, producer_postcode):
    """Return distance in miles between customer and producer, or None on failure."""
    if not customer_postcode or not producer_postcode:
        return None
    lat1, lon1 = _get_postcode_coords(customer_postcode)
    lat2, lon2 = _get_postcode_coords(producer_postcode)
    if None in (lat1, lon1, lat2, lon2):
        return None
    return _haversine_miles(lat1, lon1, lat2, lon2)


# ─────────────────────────────────────────────────────────────
# DECORATORS
# ─────────────────────────────────────────────────────────────

def producer_required(view_func):
    """Restrict a view to logged-in producers only."""
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_producer():
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapper


def customer_required(view_func):
    """Restrict a view to logged-in customers only (non-producers)."""
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.is_producer():
            messages.error(request, 'This page is for customers only.')
            return redirect('home')
        return view_func(request, *args, **kwargs)
    return wrapper


def admin_required(view_func):
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.role != 'admin' and not request.user.is_superuser:
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapper


def restaurant_required(view_func):
    """Restrict a view to logged-in restaurant accounts only."""
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.role != 'restaurant':
            messages.error(request, 'This page is for restaurant accounts only.')
            return redirect('home')
        return view_func(request, *args, **kwargs)
    return wrapper


# ─────────────────────────────────────────────────────────────
# AUTH VIEWS
# ─────────────────────────────────────────────────────────────

def register_choice(request):
    return render(request, 'auth/register_choice.html')


def register_producer(request):
    if request.method == 'POST':
        form = ProducerRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(
                request,
                f'Welcome to Bristol Food Network, {user.producer_profile.business_name}!'
            )
            return redirect('producer_dashboard')
    else:
        form = ProducerRegistrationForm()
    return render(request, 'auth/register_producer.html', {'form': form})


def register_customer(request):
    if request.method == 'POST':
        form = CustomerRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Welcome to Bristol Food Network!')
            return redirect('marketplace')
    else:
        form = CustomerRegistrationForm()
    return render(request, 'auth/register_customer.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        if request.user.role == 'admin' or request.user.is_superuser:
            return redirect('admin_dashboard')
        if request.user.is_producer():
            return redirect('producer_dashboard')
        return redirect('home')

    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Welcome back, {user.first_name or user.username}!')
            if user.role == 'admin' or user.is_superuser:
                return redirect('admin_dashboard')
            if user.is_producer():
                return redirect('producer_dashboard')
            return redirect(request.GET.get('next', 'home'))
        else:
            messages.error(request, 'Invalid username or password.')
    else:
        form = LoginForm(request)

    return render(request, 'auth/login.html', {'form': form})


@login_required
def logout_view(request):
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('login')


# ─────────────────────────────────────────────────────────────
# GENERAL
# ─────────────────────────────────────────────────────────────

def home(request):
    categories = Category.objects.all()
    featured_products = Product.objects.filter(
        availability__in=['available', 'in_season']
    ).select_related('producer', 'category').order_by('?')[:8]
    total_products = Product.objects.filter(
        availability__in=['available', 'in_season']
    ).count()

    return render(request, 'home.html', {
        'categories': categories,
        'featured_products': featured_products,
        'total_products': total_products,
    })


# ─────────────────────────────────────────────────────────────
# MARKETPLACE / PRODUCTS
# ─────────────────────────────────────────────────────────────

def marketplace(request):
    products = Product.objects.filter(
        availability__in=['available', 'in_season'],
        stock_quantity__gt=0
    ).select_related('producer', 'category')

    category_slug = request.GET.get('category', '').strip()
    search_query = request.GET.get('q', '').strip()
    organic_only = request.GET.get('organic') == '1'

    if category_slug:
        products = products.filter(category__slug=category_slug)

    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(producer__business_name__icontains=search_query)
        )

    if organic_only:
        products = products.filter(is_organic=True)

    categories = Category.objects.all()
    selected_category = Category.objects.filter(slug=category_slug).first() if category_slug else None

    return render(request, 'marketplace/browse.html', {
        'products': products,
        'categories': categories,
        'selected_category': selected_category,
        'search_query': search_query,
        'organic_only': organic_only,
    })


def product_detail(request, pk):
    product = get_object_or_404(
        Product.objects.select_related('producer', 'category').prefetch_related(
            'product_allergens',
            'recipes'
        ),
        pk=pk
    )

    # TC-013: Calculate food miles if customer is logged in
    food_miles = None
    if request.user.is_authenticated and not request.user.is_producer():
        try:
            customer_postcode = request.user.customer_profile.delivery_postcode
            producer_postcode = product.producer.farm_postcode
            food_miles = _calculate_food_miles(customer_postcode, producer_postcode)
        except Exception:
            pass

    # TC-024: Reviews
    reviews = product.reviews.filter(is_flagged=False).select_related('customer')
    avg_rating = product.reviews.aggregate(avg=Avg('rating'))['avg'] or 0
    user_review = None
    can_review = False

    if request.user.is_authenticated and not request.user.is_producer():
        user_review = Review.objects.filter(product=product, customer=request.user).first()
        can_review = not user_review and OrderItem.objects.filter(
            order__customer=request.user,
            product=product,
            order__status='delivered',
        ).exists()

    # TC-020
    producer_stories = FarmStory.objects.filter(
        producer=product.producer,
        is_approved=True
    ).order_by('-created_at')[:3]

    product_recipes = product.recipes.filter(is_approved=True).order_by('-created_at')

    return render(request, 'marketplace/product_detail.html', {
        'product': product,
        'allergens': product.product_allergens.all(),
        'form': CartItemForm(initial={'quantity': 1}),
        'food_miles': food_miles,
        'reviews': reviews,
        'avg_rating': round(avg_rating, 1),
        'user_review': user_review,
        'can_review': can_review,
        'recipes': product_recipes,
        'producer_stories': producer_stories,
    })


# ─────────────────────────────────────────────────────────────
# CART HELPERS
# ─────────────────────────────────────────────────────────────

def _get_or_create_cart(user):
    cart, _ = Cart.objects.get_or_create(customer=user)
    return cart


# ─────────────────────────────────────────────────────────────
# CART VIEWS
# ─────────────────────────────────────────────────────────────

@customer_required
def cart_view(request):
    cart = _get_or_create_cart(request.user)
    items = cart.cart_items.select_related('product', 'product__producer').all()

    customer_postcode = None
    try:
        customer_postcode = request.user.customer_profile.delivery_postcode
    except Exception:
        pass

    by_producer = {}
    total_food_miles = 0

    for item in items:
        p = item.product.producer
        if p.pk not in by_producer:
            producer_miles = None
            if customer_postcode:
                producer_miles = _calculate_food_miles(customer_postcode, p.farm_postcode)
                if producer_miles:
                    total_food_miles += producer_miles
            by_producer[p.pk] = {
                'producer': p,
                'items': [],
                'subtotal': Decimal('0'),
                'food_miles': producer_miles,
            }
        by_producer[p.pk]['items'].append(item)
        by_producer[p.pk]['subtotal'] += item.subtotal

    return render(request, 'cart/cart.html', {
        'cart': cart,
        'by_producer': by_producer.values(),
        'total_food_miles': round(total_food_miles, 1) if total_food_miles else None,
    })


@customer_required
def add_to_cart(request, product_pk):
    product = get_object_or_404(Product, pk=product_pk)

    if not product.is_available:
        messages.error(request, f'"{product.name}" is not currently available.')
        return redirect('product_detail', pk=product_pk)

    form = CartItemForm(request.POST)

    if not form.is_valid():
        messages.error(request, 'Invalid quantity.')
        return redirect('product_detail', pk=product_pk)

    qty = form.cleaned_data['quantity']

    if qty > product.stock_quantity:
        messages.warning(
            request,
            f'Not enough stock — only {product.stock_quantity} {product.get_unit_display()} available. '
            f'Please reduce the quantity.'
        )
        return redirect('product_detail', pk=product_pk)

    cart = _get_or_create_cart(request.user)
    item, created = CartItem.objects.get_or_create(
        cart=cart, product=product, defaults={'quantity': qty}
    )

    if not created:
        new_qty = item.quantity + qty
        if new_qty > product.stock_quantity:
            messages.warning(
                request,
                f'Not enough stock — only {product.stock_quantity} {product.get_unit_display()} available.'
            )
            return redirect('cart')
        item.quantity = new_qty
        item.save()

    messages.success(request, f'Added {product.name} to your cart.')
    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or 'marketplace'
    return redirect(next_url)


@customer_required
def update_cart_item(request, item_pk):
    item = get_object_or_404(CartItem, pk=item_pk, cart__customer=request.user)

    try:
        qty = int(request.POST.get('quantity', '0'))
    except Exception:
        messages.error(request, 'Invalid quantity.')
        return redirect('cart')

    if qty <= 0:
        item.delete()
        messages.info(request, 'Item removed from cart.')
        return redirect('cart')

    if qty > item.product.stock_quantity:
        messages.warning(
            request,
            f'Not enough stock — only {item.product.stock_quantity} {item.product.get_unit_display()} available '
            f'for {item.product.name}.'
        )
        return redirect('cart')

    item.quantity = qty
    item.save()
    messages.success(request, 'Cart updated.')
    return redirect('cart')


@customer_required
def remove_from_cart(request, item_pk):
    item = get_object_or_404(CartItem, pk=item_pk, cart__customer=request.user)
    item.delete()
    messages.info(request, 'Item removed from cart.')
    return redirect('cart')


# ─────────────────────────────────────────────────────────────
# CHECKOUT
# ─────────────────────────────────────────────────────────────

@customer_required
@transaction.atomic
def checkout(request):
    cart = _get_or_create_cart(request.user)

    if not cart.cart_items.exists():
        messages.error(request, 'Your cart is empty.')
        return redirect('cart')

    try:
        customer_profile = request.user.customer_profile
    except CustomerProfile.DoesNotExist:
        messages.error(request, 'Please complete your profile before checking out.')
        return redirect('cart')

    min_delivery = date.today() + timedelta(days=2)

    if request.method == 'POST':
        delivery_address = request.POST.get('delivery_address', '').strip()
        delivery_postcode = request.POST.get('delivery_postcode', '').strip()
        delivery_date_str = request.POST.get('delivery_date', '')
        special_instructions = request.POST.get('special_instructions', '').strip()

        try:
            delivery_date = datetime.strptime(delivery_date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            messages.error(request, 'Please select a valid delivery date.')
            return redirect('checkout')

        if delivery_date < min_delivery:
            messages.error(request, 'Delivery date must be at least 48 hours from now.')
            return redirect('checkout')

        items = cart.cart_items.select_related('product', 'product__producer').all()
        for cart_item in items:
            if cart_item.quantity > cart_item.product.stock_quantity:
                messages.warning(
                    request,
                    f'Not enough stock for {cart_item.product.name}. '
                    f'Available: {cart_item.product.stock_quantity} {cart_item.product.get_unit_display()}.'
                )
                return redirect('cart')

        total = cart.total

        # ── Payment: reads card choice from checkout form ──
        try:
            payment_method = request.POST.get('payment_method', 'pm_card_visa')
            payment_response = requests.post(
                'http://payment:5000/pay',
                json={
                    'amount': float(total),
                    'currency': 'gbp',
                    'payment_method': payment_method,
                    'customer_id': request.user.id,
                },
                timeout=10
            )
        except requests.RequestException:
            messages.error(request, 'Payment service is unavailable. Please try again.')
            return redirect('checkout')

        if payment_response.status_code != 200:
            try:
                payment_data = payment_response.json()
                error_message = payment_data.get('message', 'Payment failed. Please try again.')
            except Exception:
                error_message = 'Payment failed. Please try again.'
            messages.error(request, error_message)
            return redirect('checkout')
        # ──────────────────────────────────────────────────

        payment_data = payment_response.json()
        transaction_id = payment_data.get('transaction_id', '')

        order = Order.objects.create(
            customer=request.user,
            delivery_address=delivery_address,
            delivery_postcode=delivery_postcode,
            delivery_date=delivery_date,
            special_instructions=special_instructions,
            total_amount=total,
            payment_status='paid',
            payment_reference=transaction_id,
        )
        order.calculate_commission()
        order.save(update_fields=['commission_amount'])

        for cart_item in items:
            OrderItem.objects.create(
                order=order,
                product=cart_item.product,
                producer=cart_item.product.producer,
                quantity=cart_item.quantity,
                unit_price=cart_item.product.discounted_price,
                subtotal=cart_item.subtotal,
            )
            cart_item.product.stock_quantity = max(
                0,
                cart_item.product.stock_quantity - cart_item.quantity
            )
            cart_item.product.save(update_fields=['stock_quantity'])

        cart.cart_items.all().delete()

        try:
            order.sync_status_from_items(save=True)
        except Exception:
            pass

        OrderStatusHistory.objects.create(
            order=order,
            old_status='',
            new_status='pending',
            changed_by=request.user,
            notes=f'Order placed by customer. Payment reference: {transaction_id}',
        )

        messages.success(request, f'Order #{order.pk} placed successfully!')
        return redirect('order_confirmation', pk=order.pk)

    return render(request, 'cart/checkout.html', {
        'cart': cart,
        'customer_profile': customer_profile,
        'min_delivery': min_delivery,
    })


@login_required
def order_confirmation(request, pk):
    order = get_object_or_404(Order, pk=pk, customer=request.user)

    items = order.items.select_related(
        'product', 'producer', 'producer__user',
    ).order_by('producer__business_name', 'product__name')

    organisation_name = ''
    if hasattr(order.customer, 'customer_profile'):
        organisation_name = order.customer.customer_profile.organisation_name

    is_bulk_order = (order.customer.role == 'community_group')

    customer_postcode = order.delivery_postcode
    seen_producers = {}
    total_food_miles = 0

    for item in items:
        producer = item.producer
        if producer.pk not in seen_producers:
            miles = _calculate_food_miles(customer_postcode, producer.farm_postcode)
            seen_producers[producer.pk] = miles
            if miles:
                total_food_miles += miles

    total_food_miles = round(total_food_miles, 1) if total_food_miles else None

    return render(request, 'cart/order_confirmation.html', {
        'order': order,
        'items': items,
        'organisation_name': organisation_name,
        'is_bulk_order': is_bulk_order,
        'producer_food_miles': seen_producers,
        'total_food_miles': total_food_miles,
    })


# ─────────────────────────────────────────────────────────────
# CUSTOMER VIEWS
# ─────────────────────────────────────────────────────────────

@customer_required
def customer_orders(request):
    status_filter = request.GET.get('status', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()

    orders = Order.objects.filter(
        customer=request.user
    ).prefetch_related('items__product', 'items__producer').order_by('-created_at')

    if status_filter:
        orders = orders.filter(status=status_filter)

    if date_from:
        try:
            orders = orders.filter(created_at__date__gte=datetime.strptime(date_from, '%Y-%m-%d').date())
        except ValueError:
            pass

    if date_to:
        try:
            orders = orders.filter(created_at__date__lte=datetime.strptime(date_to, '%Y-%m-%d').date())
        except ValueError:
            pass

    reviewed_product_ids = set(
        Review.objects.filter(customer=request.user).values_list('product_id', flat=True)
    )

    return render(request, 'customer/orders.html', {
        'orders': orders,
        'status_filter': status_filter,
        'date_from': date_from,
        'date_to': date_to,
        'reviewed_products': reviewed_product_ids,
    })


@customer_required
def toggle_favourite_recipe(request, recipe_pk):
    recipe = get_object_or_404(Recipe, pk=recipe_pk, is_approved=True)
    favourite, created = FavouriteRecipe.objects.get_or_create(
        customer=request.user,
        recipe=recipe
    )

    if not created:
        favourite.delete()
        messages.info(request, 'Recipe removed from favourites.')
    else:
        messages.success(request, 'Recipe saved to favourites.')

    return redirect(request.META.get('HTTP_REFERER', 'marketplace'))


@customer_required
def favourite_recipes(request):
    favourites = FavouriteRecipe.objects.filter(
        customer=request.user
    ).select_related('recipe', 'recipe__producer').order_by('-created_at')

    return render(request, 'customer/favourite_recipes.html', {
        'favourites': favourites,
    })


# ─────────────────────────────────────────────────────────────
# PRODUCER VIEWS
# ─────────────────────────────────────────────────────────────

@producer_required
def producer_dashboard(request):
    from django.db.models import Sum

    profile = get_object_or_404(ProducerProfile, user=request.user)
    products = Product.objects.filter(producer=profile).order_by('-updated_at')
    pending_orders = OrderItem.objects.filter(
        producer=profile,
        producer_status='pending'
    ).select_related('order', 'order__customer', 'product').order_by('order__delivery_date')
    low_stock_products = [p for p in products if p.stock_quantity <= p.low_stock_threshold]

    all_items = OrderItem.objects.filter(producer=profile)
    fulfilled_items = all_items.filter(producer_status='delivered')
    total_revenue = all_items.aggregate(t=Sum('subtotal'))['t'] or Decimal('0')
    total_revenue = round(total_revenue, 2)
    commission_paid = round(total_revenue * Decimal('0.05'), 2)
    net_revenue = round(total_revenue - commission_paid, 2)
    total_fulfilled = fulfilled_items.count()
    total_units_sold = all_items.aggregate(t=Sum('quantity'))['t'] or 0
    best_sellers = (
        all_items
        .values('product__name')
        .annotate(units_sold=Sum('quantity'), revenue=Sum('subtotal'))
        .order_by('-revenue')[:5]
    )

    return render(request, 'producer/dashboard.html', {
        'profile': profile,
        'products': products,
        'pending_orders': pending_orders,
        'low_stock_products': low_stock_products,
        'total_products': products.count(),
        'total_fulfilled': total_fulfilled,
        'total_revenue': total_revenue,
        'net_revenue': net_revenue,
        'commission_paid': commission_paid,
        'total_units_sold': total_units_sold,
        'low_stock_count': len(low_stock_products),
        'best_sellers': best_sellers,
    })


@producer_required
def producer_products(request):
    profile = get_object_or_404(ProducerProfile, user=request.user)
    products = Product.objects.filter(producer=profile).select_related('category')
    return render(request, 'producer/products.html', {
        'products': products,
        'profile': profile,
    })


@producer_required
def product_create(request):
    profile = get_object_or_404(ProducerProfile, user=request.user)

    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.producer = profile
            product.save()
            form.save_allergens(product)
            messages.success(request, f'Product "{product.name}" listed successfully.')
            return redirect('producer_products')
    else:
        form = ProductForm()

    return render(request, 'producer/product_form.html', {'form': form, 'action': 'Add'})


@producer_required
def product_edit(request, pk):
    profile = get_object_or_404(ProducerProfile, user=request.user)
    product = get_object_or_404(Product, pk=pk, producer=profile)

    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            form.save_allergens(product)
            messages.success(request, f'"{product.name}" updated successfully.')
            return redirect('producer_products')
    else:
        form = ProductForm(instance=product)

    return render(request, 'producer/product_form.html', {
        'form': form,
        'action': 'Edit',
        'product': product,
    })


@producer_required
def producer_orders(request):
    profile = get_object_or_404(ProducerProfile, user=request.user)
    order_items = OrderItem.objects.filter(
        producer=profile
    ).select_related('order', 'order__customer', 'product').order_by('order__delivery_date')

    return render(request, 'producer/orders.html', {
        'order_items': order_items,
        'profile': profile,
    })


@producer_required
@transaction.atomic
def producer_update_order_status(request, item_pk):
    profile = get_object_or_404(ProducerProfile, user=request.user)
    item = get_object_or_404(OrderItem, pk=item_pk, producer=profile)

    STATUS_FLOW = ['pending', 'confirmed', 'ready', 'delivered']

    if request.method == 'POST':
        new_status = request.POST.get('status', '')
        notes = request.POST.get('notes', '')

        if new_status not in STATUS_FLOW:
            messages.error(request, 'Invalid status.')
            return redirect('producer_orders')

        current_idx = STATUS_FLOW.index(item.producer_status) if item.producer_status in STATUS_FLOW else 0
        new_idx = STATUS_FLOW.index(new_status)

        if new_idx > current_idx:
            old_item_status = item.producer_status
            item.producer_status = new_status
            item.producer_notes = notes
            item.save(update_fields=['producer_status', 'producer_notes'])

            OrderStatusHistory.objects.create(
                order=item.order,
                order_item=item,
                old_status=old_item_status,
                new_status=new_status,
                changed_by=request.user,
                notes=notes,
            )

            changed, old_order_status, new_order_status = item.order.sync_status_from_items(save=True)

            if changed:
                OrderStatusHistory.objects.create(
                    order=item.order,
                    order_item=None,
                    old_status=old_order_status,
                    new_status=new_order_status,
                    changed_by=request.user,
                    notes=f'Auto-updated order status based on item updates (producer: {profile.business_name}).'
                )

            messages.success(request, f'Order status updated to "{new_status}".')
        else:
            messages.error(request, 'Status can only move forward in the order lifecycle.')

    return redirect('producer_orders')


# ─────────────────────────────────────────────────────────────
# TC-020: PRODUCER CONTENT
# ─────────────────────────────────────────────────────────────

@producer_required
def producer_content(request):
    profile = get_object_or_404(ProducerProfile, user=request.user)
    recipes = Recipe.objects.filter(producer=profile).prefetch_related('products').order_by('-created_at')
    stories = FarmStory.objects.filter(producer=profile).order_by('-created_at')

    return render(request, 'producer/content.html', {
        'profile': profile,
        'recipes': recipes,
        'stories': stories,
    })


@producer_required
def recipe_create(request):
    profile = get_object_or_404(ProducerProfile, user=request.user)

    if request.method == 'POST':
        form = RecipeForm(request.POST, request.FILES)
    else:
        form = RecipeForm()

    form.fields['products'].queryset = Product.objects.filter(producer=profile).order_by('name')

    if request.method == 'POST' and form.is_valid():
        recipe = form.save(commit=False)
        recipe.producer = profile
        recipe.save()
        form.save_m2m()
        messages.success(request, 'Recipe created successfully.')
        return redirect('producer_content')

    return render(request, 'producer/recipe_form.html', {
        'form': form,
        'action': 'Add Recipe',
    })


@producer_required
def recipe_edit(request, pk):
    profile = get_object_or_404(ProducerProfile, user=request.user)
    recipe = get_object_or_404(Recipe, pk=pk, producer=profile)

    if request.method == 'POST':
        form = RecipeForm(request.POST, request.FILES, instance=recipe)
    else:
        form = RecipeForm(instance=recipe)

    form.fields['products'].queryset = Product.objects.filter(producer=profile).order_by('name')

    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Recipe updated successfully.')
        return redirect('producer_content')

    return render(request, 'producer/recipe_form.html', {
        'form': form,
        'action': 'Edit Recipe',
        'recipe': recipe,
    })


@producer_required
def farm_story_create(request):
    profile = get_object_or_404(ProducerProfile, user=request.user)

    if request.method == 'POST':
        form = FarmStoryForm(request.POST, request.FILES)
        if form.is_valid():
            story = form.save(commit=False)
            story.producer = profile
            story.save()
            messages.success(request, 'Farm story published successfully.')
            return redirect('producer_content')
    else:
        form = FarmStoryForm()

    return render(request, 'producer/farm_story_form.html', {
        'form': form,
        'action': 'Add Farm Story',
    })


@producer_required
def farm_story_edit(request, pk):
    profile = get_object_or_404(ProducerProfile, user=request.user)
    story = get_object_or_404(FarmStory, pk=pk, producer=profile)

    if request.method == 'POST':
        form = FarmStoryForm(request.POST, request.FILES, instance=story)
        if form.is_valid():
            form.save()
            messages.success(request, 'Farm story updated successfully.')
            return redirect('producer_content')
    else:
        form = FarmStoryForm(instance=story)

    return render(request, 'producer/farm_story_form.html', {
        'form': form,
        'action': 'Edit Farm Story',
        'story': story,
    })


def story_detail(request, pk):
    story = get_object_or_404(FarmStory.objects.select_related('producer'), pk=pk)
    return render(request, 'producer/story_detail.html', {
        'story': story,
    })


# ─────────────────────────────────────────────────────────────
# TC-012: PRODUCER PAYMENT SETTLEMENTS
# ─────────────────────────────────────────────────────────────

@producer_required
def producer_payments(request):
    profile = get_object_or_404(ProducerProfile, user=request.user)

    delivered_items = OrderItem.objects.filter(
        producer=profile,
        producer_status='delivered'
    ).select_related('order', 'product').order_by('-order__created_at')

    from collections import defaultdict
    import datetime as dt

    weekly = defaultdict(lambda: {
        'items': [], 'gross': Decimal('0'),
        'commission': Decimal('0'), 'net': Decimal('0'),
        'week_start': None, 'week_end': None,
    })

    for item in delivered_items:
        order_date = item.order.created_at.date()
        week_start = order_date - dt.timedelta(days=order_date.weekday())
        week_end = week_start + dt.timedelta(days=6)
        commission = round(item.subtotal * Decimal('0.05'), 2)
        net = item.subtotal - commission
        weekly[week_start]['items'].append(item)
        weekly[week_start]['gross'] += item.subtotal
        weekly[week_start]['commission'] += commission
        weekly[week_start]['net'] += net
        weekly[week_start]['week_start'] = week_start
        weekly[week_start]['week_end'] = week_end

    weekly_summaries = sorted(weekly.values(), key=lambda x: x['week_start'], reverse=True)
    total_gross = sum(w['gross'] for w in weekly_summaries)
    total_commission = sum(w['commission'] for w in weekly_summaries)
    total_net = sum(w['net'] for w in weekly_summaries)

    return render(request, 'producer/payments.html', {
        'profile': profile,
        'weekly_summaries': weekly_summaries,
        'total_gross': total_gross,
        'total_commission': total_commission,
        'total_net': total_net,
    })


@producer_required
def producer_payments_csv(request):
    import csv
    import datetime as dt
    from django.http import HttpResponse

    profile = get_object_or_404(ProducerProfile, user=request.user)
    delivered_items = OrderItem.objects.filter(
        producer=profile,
        producer_status='delivered'
    ).select_related('order', 'product').order_by('-order__created_at')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = (
        f'attachment; filename="payment_report_{profile.business_name}_{dt.date.today()}.csv"'
    )
    writer = csv.writer(response)
    writer.writerow([
        'Order #', 'Order Date', 'Delivery Date', 'Product',
        'Quantity', 'Unit Price', 'Gross Amount', 'Commission (5%)', 'Net Payment (95%)'
    ])
    for item in delivered_items:
        commission = round(item.subtotal * Decimal('0.05'), 2)
        writer.writerow([
            item.order.pk,
            item.order.created_at.strftime('%d/%m/%Y'),
            item.order.delivery_date.strftime('%d/%m/%Y'),
            item.product.name,
            item.quantity,
            item.unit_price,
            item.subtotal,
            commission,
            item.subtotal - commission,
        ])
    return response


# ─────────────────────────────────────────────────────────────
# TC-025: ADMIN COMMISSION REPORTS
# ─────────────────────────────────────────────────────────────

@admin_required
def admin_commission_report(request):
    import datetime as dt

    date_from_str = request.GET.get('date_from', '')
    date_to_str = request.GET.get('date_to', '')

    orders = Order.objects.filter(
        status__in=['delivered', 'confirmed', 'ready']
    ).prefetch_related('items__producer', 'items__product').order_by('-created_at')

    try:
        if date_from_str:
            orders = orders.filter(
                created_at__date__gte=dt.datetime.strptime(date_from_str, '%Y-%m-%d').date()
            )
        if date_to_str:
            orders = orders.filter(
                created_at__date__lte=dt.datetime.strptime(date_to_str, '%Y-%m-%d').date()
            )
    except ValueError:
        pass

    report_orders = []
    total_gross = Decimal('0')
    total_commission = Decimal('0')
    total_net = Decimal('0')

    for order in orders:
        commission = round(order.total_amount * Decimal('0.05'), 2)
        net = order.total_amount - commission
        producer_breakdown = []
        for item in order.items.all():
            item_commission = round(item.subtotal * Decimal('0.05'), 2)
            producer_breakdown.append({
                'producer': item.producer.business_name,
                'subtotal': item.subtotal,
                'commission': item_commission,
                'net': item.subtotal - item_commission,
            })
        report_orders.append({
            'order': order,
            'commission': commission,
            'net': net,
            'producer_breakdown': producer_breakdown,
        })
        total_gross += order.total_amount
        total_commission += commission
        total_net += net

    return render(request, 'admin/commission_report.html', {
        'report_orders': report_orders,
        'total_gross': total_gross,
        'total_commission': total_commission,
        'total_net': total_net,
        'date_from': date_from_str,
        'date_to': date_to_str,
    })


@admin_required
def admin_commission_csv(request):
    import csv
    import datetime as dt
    from django.http import HttpResponse

    orders = Order.objects.filter(
        status__in=['delivered', 'confirmed', 'ready']
    ).prefetch_related('items__producer', 'items__product').order_by('-created_at')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="commission_report_{dt.date.today()}.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Order #', 'Date', 'Customer', 'Producer', 'Product',
        'Item Total', 'Commission (5%)', 'Producer Payment (95%)', 'Order Status'
    ])
    for order in orders:
        for item in order.items.all():
            commission = round(item.subtotal * Decimal('0.05'), 2)
            writer.writerow([
                order.pk,
                order.created_at.strftime('%d/%m/%Y'),
                order.customer.get_full_name() or order.customer.username,
                item.producer.business_name,
                item.product.name,
                item.subtotal,
                commission,
                item.subtotal - commission,
                order.get_status_display(),
            ])
    return response


# ─────────────────────────────────────────────────────────────
# ADMIN VIEWS
# ─────────────────────────────────────────────────────────────

@admin_required
def admin_dashboard(request):
    from django.db.models import Sum

    users = User.objects.all()
    orders = Order.objects.all().order_by('-created_at')
    products = Product.objects.all()
    producers = ProducerProfile.objects.all()

    total_revenue = orders.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    total_commission = orders.aggregate(Sum('commission_amount'))['commission_amount__sum'] or 0
    total_producer_payments = total_revenue - total_commission

    low_stock = [p for p in products if p.stock_quantity <= p.low_stock_threshold]
    surplus_products = products.filter(is_surplus=True)

    return render(request, 'admin/dashboard.html', {
        'total_users': users.count(),
        'total_orders': orders.count(),
        'total_products': products.count(),
        'total_producers': producers.count(),
        'total_revenue': total_revenue,
        'total_commission': total_commission,
        'total_producer_payments': total_producer_payments,
        'recent_orders': orders[:10],
        'all_users': users,
        'all_products': products,
        'all_categories': Category.objects.all(),
        'low_stock_products': low_stock,
        'surplus_products': surplus_products,
    })


@admin_required
def admin_delete_user(request, pk):
    user = get_object_or_404(User, pk=pk)
    if user == request.user:
        messages.error(request, "You can't delete yourself.")
        return redirect('admin_dashboard')
    user.delete()
    messages.success(request, f'User "{user.username}" deleted.')
    return redirect('admin_dashboard')


@admin_required
def admin_delete_product(request, pk):
    product = get_object_or_404(Product, pk=pk)
    product.delete()
    messages.success(request, f'Product "{product.name}" deleted.')
    return redirect('admin_dashboard')


@admin_required
def admin_add_category(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        slug = request.POST.get('slug', '').strip()
        if name and slug:
            Category.objects.get_or_create(name=name, slug=slug)
            messages.success(request, f'Category "{name}" added.')
        else:
            messages.error(request, 'Name and slug are required.')
    return redirect('admin_dashboard')


@admin_required
def admin_delete_category(request, pk):
    category = get_object_or_404(Category, pk=pk)
    category.delete()
    messages.success(request, f'Category "{category.name}" deleted.')
    return redirect('admin_dashboard')


# ─────────────────────────────────────────────────────────────
# RESTAURANT — RECURRING ORDERS (TC-018)
# ─────────────────────────────────────────────────────────────

@restaurant_required
def recurring_orders_list(request):
    recurring = RecurringOrder.objects.filter(
        customer=request.user
    ).prefetch_related('template_items__product__producer')
    return render(request, 'restaurant/recurring_orders.html', {
        'recurring_orders': recurring,
    })


@restaurant_required
def recurring_order_create(request):
    if request.method == 'POST':
        form = RecurringOrderForm(request.POST)
        if form.is_valid():
            ro = form.save(commit=False)
            ro.customer = request.user
            ro.save()
            _save_recurring_items(request, ro)
            ro.next_order_date = ro.compute_next_order_date()
            ro.save(update_fields=['next_order_date'])
            messages.success(request, f'Recurring order "{ro.name}" created successfully.')
            return redirect('recurring_orders_list')
    else:
        initial = {}
        try:
            profile = request.user.customer_profile
            initial = {
                'delivery_address': profile.delivery_address,
                'delivery_postcode': profile.delivery_postcode,
            }
        except Exception:
            pass
        form = RecurringOrderForm(initial=initial)

    products = Product.objects.filter(
        availability__in=['available', 'in_season'],
        stock_quantity__gt=0
    ).select_related('producer', 'category').order_by('category__name', 'name')

    return render(request, 'restaurant/create_recurring_order.html', {
        'form': form,
        'products': products,
    })


@restaurant_required
def recurring_order_edit(request, pk):
    ro = get_object_or_404(RecurringOrder, pk=pk, customer=request.user)

    if request.method == 'POST':
        form = RecurringOrderForm(request.POST, instance=ro)
        if form.is_valid():
            ro = form.save()
            ro.template_items.all().delete()
            _save_recurring_items(request, ro)
            ro.next_order_date = ro.compute_next_order_date()
            ro.save(update_fields=['next_order_date'])
            messages.success(request, f'"{ro.name}" updated.')
            return redirect('recurring_orders_list')
    else:
        form = RecurringOrderForm(instance=ro)

    products = Product.objects.filter(
        availability__in=['available', 'in_season'],
        stock_quantity__gt=0
    ).select_related('producer', 'category').order_by('category__name', 'name')

    existing = {str(item.product_id): str(item.quantity)
                for item in ro.template_items.all()}

    return render(request, 'restaurant/edit_recurring_order.html', {
        'form': form,
        'ro': ro,
        'products': products,
        'existing_items': existing,
    })


@restaurant_required
def recurring_order_pause(request, pk):
    ro = get_object_or_404(RecurringOrder, pk=pk, customer=request.user)
    ro.is_paused = True
    ro.save(update_fields=['is_paused'])
    messages.info(request, f'"{ro.name}" paused.')
    return redirect('recurring_orders_list')


@restaurant_required
def recurring_order_resume(request, pk):
    ro = get_object_or_404(RecurringOrder, pk=pk, customer=request.user)
    ro.is_paused = False
    ro.next_order_date = ro.compute_next_order_date()
    ro.save(update_fields=['is_paused', 'next_order_date'])
    messages.success(request, f'"{ro.name}" resumed.')
    return redirect('recurring_orders_list')


@restaurant_required
def recurring_order_cancel(request, pk):
    ro = get_object_or_404(RecurringOrder, pk=pk, customer=request.user)
    name = ro.name
    ro.delete()
    messages.success(request, f'Recurring order "{name}" cancelled.')
    return redirect('recurring_orders_list')


@restaurant_required
@transaction.atomic
def recurring_order_generate(request, pk):
    ro = get_object_or_404(RecurringOrder, pk=pk, customer=request.user)

    if ro.is_paused:
        messages.warning(request, 'This recurring order is paused.')
        return redirect('recurring_orders_list')

    items = ro.template_items.select_related('product__producer').all()
    if not items.exists():
        messages.error(request, 'No products in this template — please add items first.')
        return redirect('recurring_order_edit', pk=pk)

    for t_item in items:
        if t_item.quantity > t_item.product.stock_quantity:
            messages.warning(
                request,
                f'Not enough stock for {t_item.product.name}. '
                f'Available: {t_item.product.stock_quantity} {t_item.product.get_unit_display()}. '
                f'Please reduce the quantity in the recurring order template.'
            )
            return redirect('recurring_order_edit', pk=pk)

    day_map = {
        'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
        'friday': 4, 'saturday': 5, 'sunday': 6,
    }
    target = day_map[ro.delivery_day]
    today = date.today()
    days_ahead = (target - today.weekday()) % 7 or 7
    delivery_dt = today + timedelta(days=days_ahead)

    order = Order.objects.create(
        customer=request.user,
        status='pending',
        delivery_address=ro.delivery_address,
        delivery_postcode=ro.delivery_postcode,
        delivery_date=delivery_dt,
        special_instructions=ro.special_instructions,
        recurring_order=ro,
        total_amount=Decimal('0'),
    )

    total = Decimal('0')
    for t_item in items:
        price = t_item.product.discounted_price
        sub = round(price * t_item.quantity, 2)
        total += sub
        OrderItem.objects.create(
            order=order,
            product=t_item.product,
            producer=t_item.product.producer,
            quantity=t_item.quantity,
            unit_price=price,
            subtotal=sub,
        )
        t_item.product.stock_quantity = max(0, t_item.product.stock_quantity - t_item.quantity)
        t_item.product.save(update_fields=['stock_quantity'])

    order.total_amount = total
    order.commission_amount = order.calculate_commission()
    order.save(update_fields=['total_amount', 'commission_amount'])

    try:
        order.sync_status_from_items(save=True)
    except Exception:
        pass

    ro.next_order_date = ro.compute_next_order_date()
    ro.save(update_fields=['next_order_date'])

    messages.success(
        request,
        f'Order #{order.pk} generated for delivery on {delivery_dt.strftime("%d %b %Y")}.'
    )
    return redirect('order_confirmation', pk=order.pk)


def _save_recurring_items(request, ro):
    product_ids = request.POST.getlist('product_id[]')
    quantities = request.POST.getlist('quantity[]')
    notes_list = request.POST.getlist('item_notes[]')

    for i, pid in enumerate(product_ids):
        try:
            product = Product.objects.get(pk=int(pid))
            qty = int(quantities[i]) if i < len(quantities) else 1
            note = notes_list[i] if i < len(notes_list) else ''
            if qty > 0:
                RecurringOrderItem.objects.update_or_create(
                    recurring_order=ro,
                    product=product,
                    defaults={'quantity': qty, 'notes': note},
                )
        except Exception:
            continue


# ─────────────────────────────────────────────────────────────
# TC-024: REVIEWS & RATINGS
# ─────────────────────────────────────────────────────────────

@customer_required
def submit_review(request, product_pk):
    product = get_object_or_404(Product, pk=product_pk)

    eligible_items = OrderItem.objects.filter(
        order__customer=request.user,
        product=product,
        order__status='delivered',
    )

    if not eligible_items.exists():
        messages.error(request, 'You can only review products from delivered orders.')
        return redirect('product_detail', pk=product_pk)

    existing_review = Review.objects.filter(product=product, customer=request.user).first()

    if existing_review:
        messages.warning(request, 'You have already reviewed this product. You can edit your existing review below.')
        return redirect('edit_review', pk=existing_review.pk)

    if request.method == 'POST':
        rating_str = request.POST.get('rating', '').strip()
        rating = int(rating_str) if rating_str else 0
        title = request.POST.get('title', '').strip()
        body = request.POST.get('body', '').strip()
        is_anonymous = request.POST.get('is_anonymous') == 'on'

        errors = []
        if not (1 <= rating <= 5):
            errors.append('Please select a rating between 1 and 5 stars.')
        if not title:
            errors.append('Please enter a review title.')
        if not body:
            errors.append('Please enter your review.')

        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            Review.objects.create(
                product=product,
                customer=request.user,
                order_item=eligible_items.first(),
                rating=rating,
                title=title,
                body=body,
                is_anonymous=is_anonymous,
            )
            messages.success(request, 'Your review has been submitted. Thank you!')
            return redirect('product_detail', pk=product_pk)

    return render(request, 'reviews/submit_review.html', {
        'product': product,
        'eligible_items': eligible_items,
    })


@customer_required
def edit_review(request, pk):
    review = get_object_or_404(Review, pk=pk, customer=request.user)

    if request.method == 'POST':
        rating = int(request.POST.get('rating', 0))
        title = request.POST.get('title', '').strip()
        body = request.POST.get('body', '').strip()
        is_anonymous = request.POST.get('is_anonymous') == 'on'

        errors = []
        if not (1 <= rating <= 5):
            errors.append('Please select a rating between 1 and 5 stars.')
        if not title:
            errors.append('Please enter a review title.')
        if not body:
            errors.append('Please enter your review.')

        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            review.rating = rating
            review.title = title
            review.body = body
            review.is_anonymous = is_anonymous
            review.save()
            messages.success(request, 'Your review has been updated.')
            return redirect('product_detail', pk=review.product.pk)

    return render(request, 'reviews/edit_review.html', {'review': review})


@customer_required
def delete_review(request, pk):
    review = get_object_or_404(Review, pk=pk, customer=request.user)
    product_pk = review.product.pk

    if request.method == 'POST':
        review.delete()
        messages.success(request, 'Your review has been deleted.')
        return redirect('product_detail', pk=product_pk)

    return render(request, 'reviews/delete_review.html', {'review': review})


@login_required
def flag_review(request, pk):
    review = get_object_or_404(Review, pk=pk)

    if request.method == 'POST':
        review.is_flagged = True
        review.save()
        messages.success(request, 'Review has been flagged for moderation.')
        return redirect('product_detail', pk=review.product.pk)

    return redirect('product_detail', pk=review.product.pk)


@admin_required
def admin_reviews(request):
    flagged_reviews = Review.objects.filter(is_flagged=True).select_related('product', 'customer')
    all_reviews = Review.objects.all().select_related('product', 'customer').order_by('-created_at')

    if request.method == 'POST':
        action = request.POST.get('action')
        review_pk = request.POST.get('review_pk')
        review = get_object_or_404(Review, pk=review_pk)

        if action == 'unflag':
            review.is_flagged = False
            review.save()
            messages.success(request, 'Review unflagged.')
        elif action == 'delete':
            review.delete()
            messages.success(request, 'Review deleted.')

        return redirect('admin_reviews')

    return render(request, 'reviews/admin_reviews.html', {
        'flagged_reviews': flagged_reviews,
        'all_reviews': all_reviews,
    })