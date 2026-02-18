from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.core.exceptions import PermissionDenied
from decimal import Decimal
from datetime import date, timedelta, datetime
from .models import PaymentSettlement

from .models import (
    User, Product, Category, Cart, CartItem,
    Order, OrderItem, ProducerProfile, CustomerProfile, OrderStatusHistory
)
from .forms import (
    ProducerRegistrationForm, CustomerRegistrationForm,
    LoginForm, ProductForm, CartItemForm
)


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
    """Restrict a view to logged-in customers only."""
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.is_producer():
            messages.error(request, 'This page is for customers only.')
            return redirect('home')
        return view_func(request, *args, **kwargs)
    return wrapper


# ─────────────────────────────────────────────────────────────
# AUTH VIEWS
# ─────────────────────────────────────────────────────────────

def register_choice(request):
    """Landing page — choose producer or customer registration."""
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
        return redirect('home')
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Welcome back, {user.first_name or user.username}!')
            if user.role == 'admin':
                return redirect('admin_dashboard')
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
    featured = Product.objects.filter(
        availability__in=['available', 'in_season'],
        stock_quantity__gt=0
    ).select_related('producer', 'category').order_by('-created_at')[:8]
    return render(request, 'home.html', {
        'categories': categories,
        'featured_products': featured,
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
        Product.objects.select_related('producer', 'category').prefetch_related('product_allergens'),
        pk=pk
    )
    return render(request, 'marketplace/product_detail.html', {
        'product': product,
        'allergens': product.product_allergens.all(),
        'form': CartItemForm(initial={'quantity': 1}),
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

    # Group items by producer for multi-vendor display (TC-008)
    by_producer = {}
    for item in items:
        p = item.product.producer
        if p.pk not in by_producer:
            by_producer[p.pk] = {'producer': p, 'items': [], 'subtotal': Decimal('0')}
        by_producer[p.pk]['items'].append(item)
        by_producer[p.pk]['subtotal'] += item.subtotal

    return render(request, 'cart/cart.html', {
        'cart': cart,
        'by_producer': by_producer.values(),
    })


@customer_required
def add_to_cart(request, product_pk):
    product = get_object_or_404(Product, pk=product_pk)
    if not product.is_available:
        messages.error(request, f'"{product.name}" is not currently available.')
        return redirect('product_detail', pk=product_pk)

    form = CartItemForm(request.POST)

    if form.is_valid():
        qty = form.cleaned_data['quantity']

        # ✅ TC-017: validate against stock/capacity
        if qty > product.stock_quantity:
            messages.error(
                request,
                f'Only {product.stock_quantity} {product.get_unit_display()} available.'
            )
            return redirect('product_detail', pk=product_pk)

        cart = _get_or_create_cart(request.user)
        item, created = CartItem.objects.get_or_create(
            cart=cart, product=product, defaults={'quantity': qty}
        )

        if not created:
            new_qty = item.quantity + qty
            if new_qty > product.stock_quantity:
                messages.error(
                    request,
                    f'Cannot add that much. Only {product.stock_quantity} {product.get_unit_display()} available.'
                )
                return redirect('cart')
            item.quantity = new_qty
            item.save()

        messages.success(request, f'Added {product.name} to your cart.')

    else:
        messages.error(request, 'Invalid quantity.')

    return redirect('cart')



@customer_required
@customer_required
def update_cart_item(request, item_pk):
    item = get_object_or_404(CartItem, pk=item_pk, cart__customer=request.user)
    try:
        qty = Decimal(request.POST.get('quantity', '0'))

        if qty <= 0:
            item.delete()
            messages.info(request, 'Item removed from cart.')
            return redirect('cart')

        # ✅ TC-017: validate against stock/capacity inside cart too
        if qty > item.product.stock_quantity:
            messages.error(
                request,
                f'Only {item.product.stock_quantity} {item.product.get_unit_display()} available for {item.product.name}.'
            )
            return redirect('cart')

        item.quantity = qty
        item.save()
        messages.success(request, 'Cart updated.')

    except Exception:
        messages.error(request, 'Invalid quantity.')

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

    min_delivery = date.today() + timedelta(days=2)   # 48-hour minimum lead time (TC-007)

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

        # Build the order
        items = cart.cart_items.select_related('product', 'product__producer').all()
        for cart_item in items:
            if cart_item.quantity > cart_item.product.stock_quantity:
                messages.error(
                    request,
                    f'Not enough stock for {cart_item.product.name}. '
                    f'Available: {cart_item.product.stock_quantity} {cart_item.product.get_unit_display()}.'
                )
            return redirect('cart')

        total = cart.total

        order = Order.objects.create(
            customer=request.user,
            delivery_address=delivery_address,
            delivery_postcode=delivery_postcode,
            delivery_date=delivery_date,
            special_instructions=special_instructions,
            total_amount=total,
        )
        order.calculate_commission()
        order.save()

        for cart_item in items:
            OrderItem.objects.create(
                order=order,
                product=cart_item.product,
                producer=cart_item.product.producer,
                quantity=cart_item.quantity,
                unit_price=cart_item.product.discounted_price,
                subtotal=cart_item.subtotal,
            )
            # Decrement stock (TC-011)
            cart_item.product.stock_quantity = max(
                Decimal('0'),
                cart_item.product.stock_quantity - cart_item.quantity
            )
            cart_item.product.save()

        cart.cart_items.all().delete()

        OrderStatusHistory.objects.create(
            order=order,
            old_status='',
            new_status='pending',
            changed_by=request.user,
            notes='Order placed by customer.',
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
    return render(request, 'cart/order_confirmation.html', {'order': order})


# ─────────────────────────────────────────────────────────────
# CUSTOMER VIEWS
# ─────────────────────────────────────────────────────────────

@customer_required
def customer_orders(request):
    orders = Order.objects.filter(
        customer=request.user
    ).prefetch_related('items__product', 'items__producer').order_by('-created_at')
    return render(request, 'customer/orders.html', {'orders': orders})


# ─────────────────────────────────────────────────────────────
# PRODUCER VIEWS
# ─────────────────────────────────────────────────────────────

@producer_required
def producer_dashboard(request):
    profile = get_object_or_404(ProducerProfile, user=request.user)
    products = Product.objects.filter(producer=profile).order_by('-updated_at')
    pending_orders = OrderItem.objects.filter(
        producer=profile,
        producer_status='pending'
    ).select_related('order', 'order__customer', 'product').order_by('order__delivery_date')

    # Flag low-stock products (stock at or below threshold)
    low_stock_products = [p for p in products if p.stock_quantity <= p.low_stock_threshold]

    return render(request, 'producer/dashboard.html', {
        'profile': profile,
        'products': products,
        'pending_orders': pending_orders,
        'low_stock_products': low_stock_products,
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
            old_status = item.producer_status
            item.producer_status = new_status
            item.producer_notes = notes
            item.save()
            OrderStatusHistory.objects.create(
                order=item.order,
                order_item=item,
                old_status=old_status,
                new_status=new_status,
                changed_by=request.user,
                notes=notes,
            )
            messages.success(request, f'Order status updated to "{new_status}".')
        else:
            messages.error(request, 'Status can only move forward in the order lifecycle.')

    return redirect('producer_orders')

# admin view

def admin_required(view_func):
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.role != 'admin':
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapper


@admin_required
def admin_dashboard(request):
    from django.db.models import Sum
    users = User.objects.all()
    orders = Order.objects.all().order_by('-created_at')
    products = Product.objects.all()
    producers = ProducerProfile.objects.all()

    # Financial stats
    total_revenue = orders.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    total_commission = orders.aggregate(Sum('commission_amount'))['commission_amount__sum'] or 0
    total_producer_payments = total_revenue - total_commission

    # Low stock products
    low_stock = [p for p in products if p.stock_quantity <= p.low_stock_threshold]

    # Surplus products
    from datetime import datetime
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