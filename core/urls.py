from django.urls import path
from . import views

urlpatterns = [
    # Home
    path('', views.home, name='home'),

    # Auth
    path('register/', views.register_choice, name='register'),
    path('register/producer/', views.register_producer, name='register_producer'),
    path('register/customer/', views.register_customer, name='register_customer'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Marketplace
    path('marketplace/', views.marketplace, name='marketplace'),
    path('marketplace/product/<int:pk>/', views.product_detail, name='product_detail'),

    # Cart
    path('cart/', views.cart_view, name='cart'),
    path('cart/add/<int:product_pk>/', views.add_to_cart, name='add_to_cart'),
    path('cart/update/<int:item_pk>/', views.update_cart_item, name='update_cart_item'),
    path('cart/remove/<int:item_pk>/', views.remove_from_cart, name='remove_from_cart'),

    # Checkout
    path('checkout/', views.checkout, name='checkout'),
    path('order/<int:pk>/confirmation/', views.order_confirmation, name='order_confirmation'),

    # Customer
    path('my-orders/', views.customer_orders, name='customer_orders'),

    # Producer
    path('producer/dashboard/', views.producer_dashboard, name='producer_dashboard'),
    path('producer/products/', views.producer_products, name='producer_products'),
    path('producer/products/add/', views.product_create, name='product_create'),
    path('producer/products/<int:pk>/edit/', views.product_edit, name='product_edit'),
    path('producer/orders/', views.producer_orders, name='producer_orders'),
    path('producer/orders/<int:item_pk>/status/', views.producer_update_order_status, name='producer_update_order_status'),
]