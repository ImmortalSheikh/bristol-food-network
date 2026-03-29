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

    # Restaurant — recurring orders
    path('restaurant/recurring-orders/', views.recurring_orders_list, name='recurring_orders_list'),
    path('restaurant/recurring-orders/create/', views.recurring_order_create, name='recurring_order_create'),
    path('restaurant/recurring-orders/<int:pk>/edit/', views.recurring_order_edit, name='recurring_order_edit'),
    path('restaurant/recurring-orders/<int:pk>/pause/', views.recurring_order_pause, name='recurring_order_pause'),
    path('restaurant/recurring-orders/<int:pk>/resume/', views.recurring_order_resume, name='recurring_order_resume'),
    path('restaurant/recurring-orders/<int:pk>/cancel/', views.recurring_order_cancel, name='recurring_order_cancel'),
    path('restaurant/recurring-orders/<int:pk>/generate/', views.recurring_order_generate, name='recurring_order_generate'),

    # Producer
    path('producer/dashboard/', views.producer_dashboard, name='producer_dashboard'),
    path('producer/products/', views.producer_products, name='producer_products'),
    path('producer/products/add/', views.product_create, name='product_create'),
    path('producer/products/<int:pk>/edit/', views.product_edit, name='product_edit'),
    path('producer/orders/', views.producer_orders, name='producer_orders'),
    path('producer/orders/<int:item_pk>/status/', views.producer_update_order_status, name='producer_update_order_status'),

    # TC-012: Producer Payment Settlements
    path('producer/payments/', views.producer_payments, name='producer_payments'),
    path('producer/payments/csv/', views.producer_payments_csv, name='producer_payments_csv'),

    # Admin
    path('admin-panel/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-panel/user/<int:pk>/delete/', views.admin_delete_user, name='admin_delete_user'),
    path('admin-panel/product/<int:pk>/delete/', views.admin_delete_product, name='admin_delete_product'),
    path('admin-panel/category/add/', views.admin_add_category, name='admin_add_category'),
    path('admin-panel/category/<int:pk>/delete/', views.admin_delete_category, name='admin_delete_category'),

    # TC-025: Admin Commission Reports
    path('admin-panel/commission/', views.admin_commission_report, name='admin_commission_report'),
    path('admin-panel/commission/csv/', views.admin_commission_csv, name='admin_commission_csv'),

    # Reviews (TC-024)
    path('product/<int:product_pk>/review/', views.submit_review, name='submit_review'),
    path('review/<int:pk>/edit/', views.edit_review, name='edit_review'),
    path('review/<int:pk>/delete/', views.delete_review, name='delete_review'),
    path('review/<int:pk>/flag/', views.flag_review, name='flag_review'),
    path('admin-panel/reviews/', views.admin_reviews, name='admin_reviews'),
    
]