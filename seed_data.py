"""
Run this with:  python manage.py shell < seed_data.py
Or paste it into:  python manage.py shell
"""

from django.contrib.auth.hashers import make_password
from core.models import (
    User, ProducerProfile, CustomerProfile,
    Category, Product, Cart
)
from decimal import Decimal

print("Creating test data...")

# ─────────────────────────────────────────────────────────────
# USERS
# ─────────────────────────────────────────────────────────────

# Admin
admin, _ = User.objects.get_or_create(username='admin')
admin.email = 'admin@bristol-food.test'
admin.role  = 'admin'
admin.is_staff = True
admin.is_superuser = True
admin.set_password('admin123')
admin.save()

# Producer 1
p1_user, _ = User.objects.get_or_create(username='greenvalley')
p1_user.email = 'green@farm.test'
p1_user.role  = 'producer'
p1_user.set_password('farm123')
p1_user.save()

# Producer 2
p2_user, _ = User.objects.get_or_create(username='bristolbakery')
p2_user.email = 'bakery@bristol.test'
p2_user.role  = 'producer'
p2_user.set_password('farm123')
p2_user.save()

# Producer 3
p3_user, _ = User.objects.get_or_create(username='sunnydairy')
p3_user.email = 'dairy@sunny.test'
p3_user.role  = 'producer'
p3_user.set_password('farm123')
p3_user.save()

# Restaurant customer
r1_user, _ = User.objects.get_or_create(username='cliftonkitchen')
r1_user.email = 'hello@cliftonkitchen.test'
r1_user.role  = 'restaurant'
r1_user.first_name = 'The Clifton'
r1_user.last_name  = 'Kitchen'
r1_user.set_password('rest123')
r1_user.save()

# Restaurant customer 2
r2_user, _ = User.objects.get_or_create(username='harbourside')
r2_user.email = 'info@harbourside.test'
r2_user.role  = 'restaurant'
r2_user.first_name = 'Harbourside'
r2_user.last_name  = 'Bistro'
r2_user.set_password('rest123')
r2_user.save()

# Individual customer
c1_user, _ = User.objects.get_or_create(username='janedoe')
c1_user.email = 'jane@test.com'
c1_user.role  = 'customer'
c1_user.first_name = 'Jane'
c1_user.last_name  = 'Doe'
c1_user.set_password('customer123')
c1_user.save()

# Community group
cg_user, _ = User.objects.get_or_create(username='stpauls_community')
cg_user.email = 'stpauls@community.test'
cg_user.role  = 'community_group'
cg_user.set_password('community123')
cg_user.save()

print("  ✓ Users created")

# ─────────────────────────────────────────────────────────────
# PRODUCER PROFILES
# ─────────────────────────────────────────────────────────────

p1, _ = ProducerProfile.objects.get_or_create(user=p1_user, defaults={
    'business_name': 'Green Valley Farm',
    'contact_name':  'John Hartley',
    'farm_address':  'Green Valley Lane, Chew Magna, Bristol',
    'farm_postcode': 'BS40 8SH',
    'description':   'Family-run organic farm producing seasonal vegetables since 1987.',
    'lead_time_hours': 48,
})

p2, _ = ProducerProfile.objects.get_or_create(user=p2_user, defaults={
    'business_name': 'Bristol Artisan Bakery',
    'contact_name':  'Sarah Moss',
    'farm_address':  '12 Bedminster Parade, Bristol',
    'farm_postcode': 'BS3 4HL',
    'description':   'Sourdough and artisan breads baked fresh every morning.',
    'lead_time_hours': 24,
})

p3, _ = ProducerProfile.objects.get_or_create(user=p3_user, defaults={
    'business_name': 'Sunny Hill Dairy',
    'contact_name':  'Mike Brent',
    'farm_address':  'Sunny Hill Farm, Nailsea, Bristol',
    'farm_postcode': 'BS48 1AH',
    'description':   'Fresh dairy from pasture-raised cows in the Bristol hills.',
    'lead_time_hours': 48,
})

print("  ✓ Producer profiles created")

# ─────────────────────────────────────────────────────────────
# CUSTOMER PROFILES
# ─────────────────────────────────────────────────────────────

CustomerProfile.objects.get_or_create(user=r1_user, defaults={
    'customer_type':     'restaurant',
    'organisation_name': 'The Clifton Kitchen',
    'delivery_address':  '45 Clifton Road, Clifton, Bristol',
    'delivery_postcode': 'BS8 1AB',
})

CustomerProfile.objects.get_or_create(user=r2_user, defaults={
    'customer_type':     'restaurant',
    'organisation_name': 'Harbourside Bistro',
    'delivery_address':  '8 Canons Road, Harbourside, Bristol',
    'delivery_postcode': 'BS1 5UH',
})

CustomerProfile.objects.get_or_create(user=c1_user, defaults={
    'customer_type':     'individual',
    'organisation_name': '',
    'delivery_address':  '22 Redland Road, Bristol',
    'delivery_postcode': 'BS6 6QY',
})

CustomerProfile.objects.get_or_create(user=cg_user, defaults={
    'customer_type':     'community_group',
    'organisation_name': "St Paul's Community Centre",
    'delivery_address':  '94 Grosvenor Road, St Pauls, Bristol',
    'delivery_postcode': 'BS2 8XJ',
})

print("  ✓ Customer profiles created")

# ─────────────────────────────────────────────────────────────
# CATEGORIES
# ─────────────────────────────────────────────────────────────

veg,     _ = Category.objects.get_or_create(name='Vegetables',  slug='vegetables')
fruit,   _ = Category.objects.get_or_create(name='Fruit',       slug='fruit')
dairy,   _ = Category.objects.get_or_create(name='Dairy',       slug='dairy')
bakery,  _ = Category.objects.get_or_create(name='Bakery',      slug='bakery')
herbs,   _ = Category.objects.get_or_create(name='Herbs',       slug='herbs')

print("  ✓ Categories created")

# ─────────────────────────────────────────────────────────────
# PRODUCTS  — Green Valley Farm (vegetables / fruit / herbs)
# ─────────────────────────────────────────────────────────────

products = [
    # Vegetables
    dict(producer=p1, category=veg,    name='Organic Carrots',
         description='Sweet, locally grown organic carrots. Perfect for roasting or soups.',
         price='2.50', unit='kg',    stock_quantity=150, availability='available', is_organic=True),

    dict(producer=p1, category=veg,    name='Cherry Tomatoes',
         description='Vine-ripened cherry tomatoes bursting with flavour.',
         price='3.20', unit='pack',  stock_quantity=60,  availability='available', is_organic=True),

    dict(producer=p1, category=veg,    name='Courgettes',
         description='Fresh green courgettes, harvested to order.',
         price='1.80', unit='kg',    stock_quantity=80,  availability='in_season', is_organic=True),

    dict(producer=p1, category=veg,    name='Butternut Squash',
         description='Large butternut squash, great for soups and curries.',
         price='2.00', unit='each',  stock_quantity=40,  availability='available', is_organic=False),

    dict(producer=p1, category=veg,    name='Spinach',
         description='Baby spinach leaves, harvested fresh twice weekly.',
         price='2.20', unit='pack',  stock_quantity=5,   availability='available', is_organic=True),  # low stock

    dict(producer=p1, category=fruit,  name='Strawberries',
         description='Bristol-grown strawberries, in season June–August.',
         price='4.00', unit='pack',  stock_quantity=0,   availability='out_of_season', is_organic=True),  # out of stock

    dict(producer=p1, category=herbs,  name='Fresh Basil',
         description='Fragrant basil, grown in our polytunnel year-round.',
         price='1.50', unit='bunch', stock_quantity=30,  availability='available', is_organic=True),

    dict(producer=p1, category=herbs,  name='Flat-leaf Parsley',
         description='Fresh flat-leaf parsley, cut to order.',
         price='1.20', unit='bunch', stock_quantity=25,  availability='available', is_organic=True),

    # Bakery — Bristol Artisan Bakery
    dict(producer=p2, category=bakery, name='Sourdough Loaf',
         description='Classic white sourdough, long-fermented for depth of flavour.',
         price='4.50', unit='each',  stock_quantity=20,  availability='available', is_organic=False),

    dict(producer=p2, category=bakery, name='Rye & Seed Loaf',
         description='Dense rye loaf packed with sunflower and pumpkin seeds.',
         price='5.00', unit='each',  stock_quantity=15,  availability='available', is_organic=False),

    dict(producer=p2, category=bakery, name='Croissants (6-pack)',
         description='Buttery all-butter croissants, baked from scratch each morning.',
         price='7.50', unit='pack',  stock_quantity=10,  availability='available', is_organic=False),

    # Dairy — Sunny Hill Dairy
    dict(producer=p3, category=dairy,  name='Whole Milk (2L)',
         description='Fresh whole milk from our pasture-raised Friesian herd.',
         price='1.80', unit='litre',  stock_quantity=200, availability='available', is_organic=False),

    dict(producer=p3, category=dairy,  name='Mature Cheddar',
         description='12-month aged cheddar with a rich, sharp flavour.',
         price='6.50', unit='kg',    stock_quantity=30,  availability='available', is_organic=False),

    dict(producer=p3, category=dairy,  name='Natural Yoghurt',
         description='Thick, creamy natural yoghurt — no additives.',
         price='2.80', unit='each',  stock_quantity=45,  availability='available', is_organic=False),

    dict(producer=p3, category=dairy,  name='Unsalted Butter',
         description='Churned fresh from our own cream.',
         price='3.20', unit='each',  stock_quantity=50,  availability='available', is_organic=False),
]

for p in products:
    price = p.pop('price')
    Product.objects.get_or_create(
        name=p['name'], producer=p['producer'],
        defaults={**p, 'price': Decimal(price)}
    )

print("  ✓ Products created (including 1 low-stock and 1 out-of-season for testing alerts)")

# ─────────────────────────────────────────────────────────────
# CARTS  (so customers can go straight to shopping)
# ─────────────────────────────────────────────────────────────

for user in [r1_user, r2_user, c1_user, cg_user]:
    Cart.objects.get_or_create(customer=user)

print("  ✓ Carts created")

# ─────────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────────

print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  TEST DATA READY — Login credentials
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Admin:        admin          / admin123
  Producer 1:   greenvalley    / farm123    (Green Valley Farm)
  Producer 2:   bristolbakery  / farm123    (Bristol Artisan Bakery)
  Producer 3:   sunnydairy     / farm123    (Sunny Hill Dairy)
  Restaurant 1: cliftonkitchen / rest123    (The Clifton Kitchen)
  Restaurant 2: harbourside    / rest123    (Harbourside Bistro)
  Customer:     janedoe        / customer123
  Community:    stpauls_community / community123
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Products include:
    - 1 out-of-season item (Strawberries) → tests unavailability alert
    - 1 low-stock item (Spinach, qty=5)   → tests low stock warning
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
