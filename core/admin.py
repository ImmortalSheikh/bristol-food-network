from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User, ProducerProfile, CustomerProfile, Category,
    Product, ProductAllergen, Order, OrderItem,
    Cart, CartItem, PaymentSettlement, OrderStatusHistory
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'role', 'is_active', 'date_joined')
    list_filter = ('role', 'is_active', 'is_staff')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Role & Contact', {'fields': ('role', 'phone', 'address', 'postcode')}),
    )


@admin.register(ProducerProfile)
class ProducerProfileAdmin(admin.ModelAdmin):
    list_display = ('business_name', 'contact_name', 'farm_postcode', 'lead_time_hours')
    search_fields = ('business_name', 'contact_name', 'farm_postcode')


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'customer_type', 'organisation_name', 'delivery_postcode')
    list_filter = ('customer_type',)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


class ProductAllergenInline(admin.TabularInline):
    model = ProductAllergen
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'producer', 'category', 'price', 'unit',
        'stock_quantity', 'availability', 'is_organic', 'is_surplus'
    )
    list_filter = ('availability', 'is_organic', 'is_surplus', 'category')
    search_fields = ('name', 'producer__business_name', 'description')
    inlines = [ProductAllergenInline]
    readonly_fields = ('created_at', 'updated_at')


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('subtotal',)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'pk', 'customer', 'status', 'payment_status',
        'total_amount', 'commission_amount', 'delivery_date', 'created_at'
    )
    list_filter = ('status', 'payment_status')
    search_fields = ('customer__username', 'customer__email')
    readonly_fields = ('commission_amount', 'created_at', 'updated_at')
    inlines = [OrderItemInline]


@admin.register(PaymentSettlement)
class PaymentSettlementAdmin(admin.ModelAdmin):
    list_display = (
        'producer', 'week_start', 'week_end',
        'gross_amount', 'commission_amount', 'net_amount', 'status'
    )
    list_filter = ('status',)
    search_fields = ('producer__business_name',)


@admin.register(OrderStatusHistory)
class OrderStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ('order', 'old_status', 'new_status', 'changed_by', 'changed_at')
    readonly_fields = ('changed_at',)