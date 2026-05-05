import os, math
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import (
    Category, ProducerProfile, CustomerProfile,
    Product, Recipe, FarmStory,
)

User = get_user_model()


# ── Pillow image generation ────────────────────────────────────────────────────

def _make_image(product_name, category_slug, producer_name, filepath):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return False

    PALETTES = {
        'vegetables':           ((34, 85, 34),    (88, 160, 88),   (200, 230, 100), (255, 255, 255)),
        'dairy-eggs':           ((180, 130, 40),  (230, 190, 90),  (255, 240, 180), (60,  40,  10)),
        'bakery':               ((120, 70,  20),  (190, 130, 70),  (240, 210, 160), (255, 245, 230)),
        'preserves-jams':       ((140, 30,  60),  (210, 80,  100), (255, 180, 160), (255, 240, 235)),
        'seasonal-specialties': ((30,  100, 110), (60,  170, 160), (160, 230, 210), (240, 255, 252)),
        'meat-poultry':         ((100, 40,  30),  (170, 80,  60),  (230, 170, 140), (255, 240, 235)),
        'fruit':                ((180, 50,  30),  (230, 110, 60),  (255, 210, 130), (60,  20,  10)),
        'drinks':               ((30,  60,  120), (60,  110, 190), (150, 200, 240), (240, 248, 255)),
    }
    CAT_LABELS = {
        'vegetables': 'Vegetables', 'dairy-eggs': 'Dairy & Eggs',
        'bakery': 'Bakery', 'preserves-jams': 'Preserves & Jams',
        'seasonal-specialties': 'Seasonal Specialties', 'meat-poultry': 'Meat & Poultry',
        'fruit': 'Fruit', 'drinks': 'Drinks',
    }

    FONT_BOLD   = '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf'
    FONT_REG    = '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf'
    FONT_ITALIC = '/usr/share/fonts/truetype/liberation/LiberationSans-Italic.ttf'

    palette  = PALETTES.get(category_slug, PALETTES['vegetables'])
    dark, light, accent, text_col = palette
    cat_label = CAT_LABELS.get(category_slug, category_slug.replace('-', ' ').title())
    W, H = 600, 500

    def lerp(c1, c2, t):
        return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))

    img = Image.new('RGB', (W, H))
    draw = ImageDraw.Draw(img)
    for y in range(H):
        draw.line([(0, y), (W, y)], fill=lerp(dark, light, y / H))

    overlay = Image.new('RGB', (W, H))
    od = ImageDraw.Draw(overlay)
    for y in range(H):
        od.line([(0, y), (W, y)], fill=lerp(dark, light, y / H))
    img = Image.blend(img, overlay, 0.55)
    draw = ImageDraw.Draw(img)

    # Decorative circles
    circle_col = tuple(min(255, c + 40) for c in light)
    draw.ellipse([W - 200, -100, W + 60, 160], fill=circle_col)
    draw.ellipse([-40, H - 130, 120, H + 30],  fill=circle_col)

    # Accent bars
    draw.rectangle([0, 0, W, 8],    fill=accent)
    draw.rectangle([0, H - 8, W, H], fill=accent)
    draw.rectangle([0, 0, 5, H],    fill=tuple(min(255, c + 60) for c in accent))

    # Category pill
    try:
        font_cat = ImageFont.truetype(FONT_BOLD, 18)
    except Exception:
        font_cat = ImageFont.load_default()
    cb = draw.textbbox((0, 0), cat_label.upper(), font=font_cat)
    pw, ph = cb[2] - cb[0] + 32, cb[3] - cb[1] + 14
    draw.rounded_rectangle([24, 24, 24 + pw, 24 + ph], radius=ph // 2, fill=accent)
    draw.text((40, 31), cat_label.upper(), font=font_cat,
              fill=tuple(max(0, c - 120) for c in accent))

    # Product name
    try:
        font_title = ImageFont.truetype(FONT_BOLD, 52)
    except Exception:
        font_title = ImageFont.load_default()

    def wrap(text, font, max_w):
        words, lines, current = text.split(), [], []
        for word in words:
            test = ' '.join(current + [word])
            if draw.textbbox((0, 0), test, font=font)[2] <= max_w or not current:
                current.append(word)
            else:
                lines.append(' '.join(current))
                current = [word]
        if current:
            lines.append(' '.join(current))
        return lines

    lines = wrap(product_name, font_title, W - 100)
    if len(lines) > 3:
        try:
            font_title = ImageFont.truetype(FONT_BOLD, 40)
        except Exception:
            pass
        lines = wrap(product_name, font_title, W - 100)

    line_h = draw.textbbox((0, 0), 'Ag', font=font_title)[3] + 8
    start_y = (H - line_h * len(lines)) // 2 - 20
    for i, line in enumerate(lines):
        lw = draw.textbbox((0, 0), line, font=font_title)[2]
        x, y = (W - lw) // 2, start_y + i * (line_h + 4)
        draw.text((x + 3, y + 3), line, font=font_title,
                  fill=tuple(max(0, c - 80) for c in dark))
        draw.text((x, y), line, font=font_title, fill=text_col)

    div_y = start_y + line_h * len(lines) + 24
    draw.rectangle([50, div_y, W - 50, div_y + 2], fill=accent)

    try:
        font_prod = ImageFont.truetype(FONT_ITALIC, 22)
        font_small = ImageFont.truetype(FONT_REG, 16)
    except Exception:
        font_prod = font_small = ImageFont.load_default()

    pt = f'by {producer_name}'
    pw2 = draw.textbbox((0, 0), pt, font=font_prod)[2]
    draw.text(((W - pw2) // 2, div_y + 12), pt, font=font_prod,
              fill=tuple(min(255, c + 160) for c in dark))

    nt = 'Bristol Food Network'
    nw = draw.textbbox((0, 0), nt, font=font_small)[2]
    draw.text(((W - nw) // 2, H - 36), nt, font=font_small,
              fill=tuple(min(255, c + 100) for c in accent))

    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    img.save(filepath, 'JPEG', quality=90)
    return True


# ── Data ──────────────────────────────────────────────────────────────────────

CATEGORIES = [
    ('Vegetables',           'vegetables',           '🥦'),
    ('Dairy & Eggs',         'dairy-eggs',           '🥚'),
    ('Bakery',               'bakery',               '🍞'),
    ('Preserves & Jams',     'preserves-jams',       '🍯'),
    ('Seasonal Specialties', 'seasonal-specialties', '🌿'),
    ('Meat & Poultry',       'meat-poultry',         '🥩'),
    ('Fruit',                'fruit',                '🍎'),
    ('Drinks',               'drinks',               '🍵'),
]

PRODUCT_FILENAMES = {
    'Organic Carrots':          'carrots.jpg',
    'Baby Spinach':             'spinach.jpg',
    'Cherry Tomatoes':          'cherry_tomatoes.jpg',
    'New Potatoes':             'potatoes.jpg',
    'Free-Range Hen Eggs':      'hen_eggs.jpg',
    'Whole Milk':               'whole_milk.jpg',
    'Mature Cheddar Cheese':    'cheddar.jpg',
    'Natural Yoghurt':          'yoghurt.jpg',
    'Sourdough Loaf':           'sourdough.jpg',
    'Wholemeal Bread':          'wholemeal.jpg',
    'Butter Croissants':        'croissants.jpg',
    'Cinnamon Rolls':           'cinnamon_rolls.jpg',
    'Strawberry Jam':           'strawberry_jam.jpg',
    'Raspberry Jam':            'raspberry_jam.jpg',
    'Lemon Curd':               'lemon_curd.jpg',
    'Apple Chutney':            'apple_chutney.jpg',
    'Fresh Asparagus':          'asparagus.jpg',
    'Butternut Squash':         'butternut_squash.jpg',
    'Mixed Wild Mushrooms':     'mushrooms.jpg',
    'Fresh Herb Bundle':        'fresh_herbs.jpg',
    'Whole Free-Range Chicken': 'whole_chicken.jpg',
    'Pork Sausages':            'sausages.jpg',
    'Beef Mince':               'beef_mince.jpg',
    'Lamb Chops':               'lamb_chops.jpg',
    'Strawberries':             'strawberries.jpg',
    'Raspberries':              'raspberries.jpg',
    'Cox Apples':               'apples.jpg',
    'Conference Pears':         'pears.jpg',
    'Fresh Apple Juice':        'apple_juice.jpg',
    'Elderflower Cordial':      'elderflower_cordial.jpg',
    'Blackcurrant Juice':       'blackcurrant_juice.jpg',
    'Fresh Lemonade':           'lemonade.jpg',
}


class Command(BaseCommand):
    help = 'Seed the database with full demo data — 2 producers, 32 products, 3 customers, 10 recipes, 10 farm stories.'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true',
                            help='Delete all existing products, recipes and stories before seeding.')

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('\nSeeding Bristol Food Network...\n'))

        if options.get('reset'):
            from core.models import (
                Recipe, FarmStory, OrderItem, Order,
                CartItem, Cart, Review, FavouriteRecipe,
            )
            # Must delete in dependency order to avoid ProtectedError
            CartItem.objects.all().delete()
            Cart.objects.all().delete()
            Review.objects.all().delete()
            FavouriteRecipe.objects.all().delete()
            OrderItem.objects.all().delete()
            Order.objects.all().delete()
            Product.objects.all().delete()
            Recipe.objects.all().delete()
            FarmStory.objects.all().delete()
            self.stdout.write('  [reset] Cleared orders, products, recipes and stories.')

        # ── Categories ────────────────────────────────────────────────────────
        for name, slug, icon in CATEGORIES:
            cat, created = Category.objects.get_or_create(
                slug=slug, defaults={'name': name, 'icon': icon}
            )
            if created:
                self.stdout.write(f'  [+] Category: {name}')

        # ── Admin ─────────────────────────────────────────────────────────────
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser(
                username='admin', email='admin@bristolfoodnetwork.com',
                password='Admin123!', role='admin',
            )
            self.stdout.write('  [+] Admin: admin / Admin123!')

        # ── Producer 1 ────────────────────────────────────────────────────────
        u1, created = User.objects.get_or_create(
            username='producer1',
            defaults=dict(role='producer', first_name='Jane', last_name='Smith',
                          email='jane@bristolvalleyfarm.com', phone='01179 123456'),
        )
        if created:
            u1.set_password('TestPass123!')
            u1.save()
            self.stdout.write('  [+] Producer 1: producer1 / TestPass123!')
        ProducerProfile.objects.get_or_create(
            user=u1,
            defaults=dict(
                business_name='Bristol Valley Farm',
                contact_name='Jane Smith',
                farm_address='Valley Road, Clifton, Bristol',
                farm_postcode='BS8 2TR',
                description='Third-generation family farm nestled in the Avon Valley. '
                            'We grow seasonal vegetables, raise free-range hens and keep bees.',
                lead_time_hours=48,
            ),
        )

        # ── Producer 2 ────────────────────────────────────────────────────────
        u2, created = User.objects.get_or_create(
            username='producer2',
            defaults=dict(role='producer', first_name='Tom', last_name='Fletcher',
                          email='tom@greenmeadowsorganic.com', phone='01179 654321'),
        )
        if created:
            u2.set_password('TestPass123!')
            u2.save()
            self.stdout.write('  [+] Producer 2: producer2 / TestPass123!')
        ProducerProfile.objects.get_or_create(
            user=u2,
            defaults=dict(
                business_name='Green Meadows Organic',
                contact_name='Tom Fletcher',
                farm_address='Meadow Lane, Cotham, Bristol',
                farm_postcode='BS6 5RQ',
                description='Certified organic smallholding specialising in heritage fruit, '
                            'artisan preserves and cold-pressed drinks since 2005.',
                lead_time_hours=72,
            ),
        )

        # ── Customers ─────────────────────────────────────────────────────────
        if not User.objects.filter(username='customer1').exists():
            u = User.objects.create_user(
                username='customer1', password='TestPass123!', role='customer',
                first_name='Robert', last_name='Johnson',
                email='robert@email.com', phone='07700 900123',
            )
            CustomerProfile.objects.create(
                user=u, customer_type='individual',
                delivery_address='45 Park Street, Bristol',
                delivery_postcode='BS1 5JG',
            )
            self.stdout.write('  [+] Customer: customer1 / TestPass123!')

        if not User.objects.filter(username='restaurant1').exists():
            u = User.objects.create_user(
                username='restaurant1', password='TestPass123!', role='restaurant',
                first_name='Sophie', last_name='Martinez',
                email='sophie@harboursidetable.com', phone='01179 334455',
            )
            CustomerProfile.objects.create(
                user=u, customer_type='restaurant',
                organisation_name='The Harbourside Table',
                delivery_address='1 Wapping Wharf, Bristol Harbourside',
                delivery_postcode='BS1 6UD',
            )
            self.stdout.write('  [+] Restaurant: restaurant1 / TestPass123!')

        if not User.objects.filter(username='community1').exists():
            u = User.objects.create_user(
                username='community1', password='TestPass123!', role='community_group',
                first_name='Marcus', last_name='Osei',
                email='marcus@stpaulsfc.org', phone='07900 112233',
            )
            CustomerProfile.objects.create(
                user=u, customer_type='community_group',
                organisation_name="St Paul's Food Co-op",
                delivery_address='72 Grosvenor Road, St Pauls, Bristol',
                delivery_postcode='BS2 8XJ',
            )
            self.stdout.write('  [+] Community group: community1 / TestPass123!')

        # ── Products ──────────────────────────────────────────────────────────
        p1 = ProducerProfile.objects.get(user__username='producer1')
        p2 = ProducerProfile.objects.get(user__username='producer2')

        def cat(slug):
            return Category.objects.get(slug=slug)

        PRODUCTS = [
            # Vegetables
            dict(producer=p1, category=cat('vegetables'), name='Organic Carrots',
                 description='Sweet, freshly pulled organic carrots. Great raw, roasted or in soups.',
                 price='1.80', unit='kg', stock_quantity=80, availability='available', is_organic=True),
            dict(producer=p1, category=cat('vegetables'), name='Baby Spinach',
                 description='Tender organic baby spinach leaves, washed and ready to use.',
                 price='2.00', unit='each', stock_quantity=50, availability='available', is_organic=True),
            dict(producer=p2, category=cat('vegetables'), name='Cherry Tomatoes',
                 description='Ripe, sweet cherry tomatoes grown in our polytunnel. Packed with flavour.',
                 price='2.50', unit='each', stock_quantity=60, availability='in_season', is_organic=False),
            dict(producer=p2, category=cat('vegetables'), name='New Potatoes',
                 description='Fresh, waxy new potatoes. Perfect boiled with butter and mint.',
                 price='2.20', unit='kg', stock_quantity=100, availability='available', is_organic=False),
            # Dairy & Eggs
            dict(producer=p1, category=cat('dairy-eggs'), name='Free-Range Hen Eggs',
                 description='A dozen large eggs from our flock of free-range hens. Deep orange yolks, collected daily.',
                 price='3.50', unit='dozen', stock_quantity=80, availability='available', is_organic=True),
            dict(producer=p1, category=cat('dairy-eggs'), name='Whole Milk',
                 description='Fresh, full-fat whole milk from our grass-fed herd. Unhomogenised, non-pasteurised.',
                 price='1.20', unit='litre', stock_quantity=60, availability='available', is_organic=True),
            dict(producer=p2, category=cat('dairy-eggs'), name='Mature Cheddar Cheese',
                 description='Aged 12 months for a sharp, nutty flavour. Made with our own herd\'s milk.',
                 price='6.00', unit='each', stock_quantity=25, availability='available', is_organic=False),
            dict(producer=p2, category=cat('dairy-eggs'), name='Natural Yoghurt',
                 description='Thick, creamy natural yoghurt made fresh each week. No additives.',
                 price='2.80', unit='each', stock_quantity=30, availability='available', is_organic=True),
            # Bakery
            dict(producer=p1, category=cat('bakery'), name='Sourdough Loaf',
                 description='Long-fermented white sourdough with a crisp crust and open crumb. Baked fresh daily.',
                 price='4.50', unit='each', stock_quantity=15, availability='available', is_organic=False),
            dict(producer=p1, category=cat('bakery'), name='Wholemeal Bread',
                 description='Soft, hearty wholemeal loaf made with stoneground flour. Sliced or unsliced.',
                 price='3.50', unit='each', stock_quantity=20, availability='available', is_organic=False),
            dict(producer=p2, category=cat('bakery'), name='Butter Croissants',
                 description='Light, flaky all-butter croissants baked fresh each morning. Pack of 4.',
                 price='5.00', unit='pack', stock_quantity=18, availability='available', is_organic=False),
            dict(producer=p2, category=cat('bakery'), name='Cinnamon Rolls',
                 description='Soft, sticky cinnamon rolls with cream cheese icing. Pack of 4.',
                 price='5.50', unit='pack', stock_quantity=12, availability='available', is_organic=False),
            # Preserves & Jams
            dict(producer=p1, category=cat('preserves-jams'), name='Strawberry Jam',
                 description='Classic homemade strawberry jam using British strawberries. Low sugar recipe.',
                 price='3.50', unit='each', stock_quantity=40, availability='available', is_organic=False),
            dict(producer=p1, category=cat('preserves-jams'), name='Raspberry Jam',
                 description='Sharp, fruity raspberry jam. Wonderful on toast, scones or stirred into yoghurt.',
                 price='3.80', unit='each', stock_quantity=35, availability='available', is_organic=False),
            dict(producer=p2, category=cat('preserves-jams'), name='Lemon Curd',
                 description='Tangy, buttery lemon curd made with free-range eggs. Rich and intensely lemony.',
                 price='4.00', unit='each', stock_quantity=28, availability='available', is_organic=False),
            dict(producer=p2, category=cat('preserves-jams'), name='Apple Chutney',
                 description='Sweet and spiced apple chutney. Perfect with cheese, cold meats or pork.',
                 price='3.80', unit='each', stock_quantity=32, availability='available', is_organic=False),
            # Seasonal Specialties
            dict(producer=p1, category=cat('seasonal-specialties'), name='Fresh Asparagus',
                 description='Bristol-grown asparagus, cut fresh each morning. British asparagus season only.',
                 price='4.50', unit='bunch', stock_quantity=30, availability='in_season', is_organic=True),
            dict(producer=p1, category=cat('seasonal-specialties'), name='Butternut Squash',
                 description='Grown on our farm and cured for sweetness. Keeps for months. Great roasted.',
                 price='3.00', unit='each', stock_quantity=25, availability='available', is_organic=True),
            dict(producer=p2, category=cat('seasonal-specialties'), name='Mixed Wild Mushrooms',
                 description='A seasonal mix of chanterelle, oyster and porcini. Foraged locally.',
                 price='6.50', unit='each', stock_quantity=15, availability='in_season', is_organic=False),
            dict(producer=p2, category=cat('seasonal-specialties'), name='Fresh Herb Bundle',
                 description='A generous bundle of fresh seasonal herbs — rosemary, thyme, sage and flat-leaf parsley.',
                 price='2.50', unit='bunch', stock_quantity=40, availability='available', is_organic=True),
            # Meat & Poultry
            dict(producer=p1, category=cat('meat-poultry'), name='Whole Free-Range Chicken',
                 description='Slow-grown outdoor-reared chicken, typically 1.8–2.2 kg. Fed on grain and pasture.',
                 price='14.50', unit='each', stock_quantity=12, availability='available', is_organic=False),
            dict(producer=p1, category=cat('meat-poultry'), name='Pork Sausages',
                 description='Hand-linked pork sausages from our rare-breed Saddleback pigs. Pack of 6.',
                 price='6.00', unit='pack', stock_quantity=20, availability='available', is_organic=False),
            dict(producer=p2, category=cat('meat-poultry'), name='Beef Mince',
                 description='Freshly minced beef from grass-fed cattle. 500g. Lean and full of flavour.',
                 price='7.50', unit='each', stock_quantity=18, availability='available', is_organic=False),
            dict(producer=p2, category=cat('meat-poultry'), name='Lamb Chops',
                 description='Pasture-raised local lamb chops. Pack of 2. Great on the barbecue or pan-fried.',
                 price='9.00', unit='pack', stock_quantity=14, availability='available', is_organic=False),
            # Fruit
            dict(producer=p1, category=cat('fruit'), name='Strawberries',
                 description='Sweet, sun-ripened British strawberries. Picked fresh each morning.',
                 price='3.50', unit='each', stock_quantity=40, availability='in_season', is_organic=True),
            dict(producer=p1, category=cat('fruit'), name='Raspberries',
                 description='Fresh raspberries from our fruit cage. Delicate and intensely flavoured.',
                 price='3.80', unit='each', stock_quantity=30, availability='in_season', is_organic=True),
            dict(producer=p2, category=cat('fruit'), name='Cox Apples',
                 description='Classic English Cox apples from our heritage orchard. Sweet, crisp and aromatic.',
                 price='2.80', unit='kg', stock_quantity=70, availability='in_season', is_organic=False),
            dict(producer=p2, category=cat('fruit'), name='Conference Pears',
                 description='Sweet, juicy pears from our small orchard. Best eaten when slightly soft.',
                 price='3.00', unit='kg', stock_quantity=50, availability='in_season', is_organic=False),
            # Drinks
            dict(producer=p1, category=cat('drinks'), name='Fresh Apple Juice',
                 description='Cold-pressed apple juice made from our own orchard apples. 750ml. No added sugar.',
                 price='4.00', unit='each', stock_quantity=35, availability='available', is_organic=False),
            dict(producer=p1, category=cat('drinks'), name='Elderflower Cordial',
                 description='Hand-picked elderflower steeped in sugar and lemon. Dilute 1:10. 500ml bottle.',
                 price='5.00', unit='each', stock_quantity=25, availability='in_season', is_organic=False),
            dict(producer=p2, category=cat('drinks'), name='Blackcurrant Juice',
                 description='Pure pressed blackcurrant juice from our fruit bushes. Rich and full of vitamin C.',
                 price='4.50', unit='each', stock_quantity=20, availability='in_season', is_organic=True),
            dict(producer=p2, category=cat('drinks'), name='Fresh Lemonade',
                 description='Old-fashioned pressed lemonade made with unwaxed lemons and cane sugar. 750ml.',
                 price='3.50', unit='each', stock_quantity=30, availability='available', is_organic=False),
        ]

        from django.conf import settings
        media_root = getattr(settings, 'MEDIA_ROOT', '/app/media')
        products_dir = os.path.join(str(media_root), 'products')
        os.makedirs(products_dir, exist_ok=True)

        created_products = 0
        for data in PRODUCTS:
            name = data['name']
            producer = data['producer']
            filename = PRODUCT_FILENAMES.get(name)
            if not Product.objects.filter(name=name, producer=producer).exists():
                img_field = f'products/{filename}' if filename else ''
                product = Product.objects.create(**{**data, 'image': img_field})
                created_products += 1
                # Generate image
                if filename:
                    filepath = os.path.join(products_dir, filename)
                    ok = _make_image(name, product.category.slug, producer.business_name, filepath)
                    if not ok:
                        self.stdout.write(self.style.WARNING(f'    Pillow not available, skipping image for {name}'))

        self.stdout.write(f'  [+] Created {created_products} products')

        # ── Recipes ───────────────────────────────────────────────────────────
        RECIPES = [
            dict(producer=p1, title='Scrambled Eggs on Sourdough Toast',
                 description='The simplest, most satisfying breakfast — done properly with fresh eggs and good bread.',
                 ingredients='4 Free-Range Hen Eggs\n2 slices Sourdough Loaf\n30g butter\n2 tbsp whole milk\nSalt and black pepper\nChives to serve',
                 instructions='1. Toast the sourdough while you make the eggs.\n2. Crack eggs into a cold saucepan with butter, milk, salt and pepper.\n3. Place over low heat and stir constantly with a spatula.\n4. Remove from heat just before they look fully set — carry-over heat will finish them.\n5. Pile onto toast and scatter with chives.',
                 seasonal_tag='All Year', storage_guidance='Eat immediately.'),
            dict(producer=p1, title='Roast Chicken with Herb Stuffing and New Potatoes',
                 description='A proper Sunday roast using the best ingredients from the farm.',
                 ingredients='1 Whole Free-Range Chicken (approx 1.8kg)\n1 Fresh Herb Bundle (rosemary, thyme, sage)\n500g New Potatoes\n1 lemon, halved\n4 garlic cloves\n3 tbsp olive oil\nSalt and pepper',
                 instructions='1. Preheat oven to 200°C.\n2. Pat chicken dry. Push half the herbs and garlic inside the cavity along with the lemon halves.\n3. Rub skin with olive oil, salt and pepper.\n4. Toss new potatoes with oil and remaining herbs in a roasting tin.\n5. Sit chicken on top of the potatoes.\n6. Roast 1 hour 20 mins. Rest 15 mins before carving.',
                 seasonal_tag='All Year', storage_guidance='Leftovers keep 3 days in the fridge.'),
            dict(producer=p1, title='Honey-Glazed Roast Carrots',
                 description='Simple roasted carrots transformed into something special with a good glaze.',
                 ingredients='500g Organic Carrots, peeled and halved lengthways\n2 tbsp butter\n1 tbsp honey\n1 tsp fresh thyme leaves\nSalt and black pepper\nJuice of half a lemon',
                 instructions='1. Preheat oven to 200°C.\n2. Toss carrots with melted butter, honey, thyme, salt and pepper.\n3. Spread in a single layer on a roasting tray.\n4. Roast 25–30 mins, turning halfway, until caramelised at the edges.\n5. Squeeze over lemon juice before serving.',
                 seasonal_tag='All Year', storage_guidance='Keeps in fridge 2 days. Reheat in oven.'),
            dict(producer=p1, title='Sourdough French Toast with Strawberry Jam',
                 description='Transform day-old sourdough into a gorgeous weekend brunch.',
                 ingredients='4 thick slices Sourdough Loaf\n3 Free-Range Hen Eggs\n100ml Whole Milk\n1 tsp vanilla extract\n1 tsp cinnamon\nButter for frying\n4 tbsp Strawberry Jam\nNatural Yoghurt to serve',
                 instructions='1. Beat eggs with milk, vanilla and cinnamon in a wide bowl.\n2. Soak sourdough slices 2 mins each side until saturated.\n3. Fry in foaming butter over medium heat 3 mins per side until golden brown.\n4. Serve topped with strawberry jam and a dollop of yoghurt.',
                 seasonal_tag='All Year', storage_guidance='Best eaten immediately.'),
            dict(producer=p1, title='Pork Sausage Traybake with Butternut Squash',
                 description='A brilliant one-pan supper — the squash turns sticky and sweet alongside the sausages.',
                 ingredients='1 pack Pork Sausages\n1 Butternut Squash, peeled and cubed\n2 red onions, cut into wedges\n4 garlic cloves, unpeeled\nFresh rosemary from your herb bundle\n3 tbsp olive oil\nSalt and pepper',
                 instructions='1. Preheat oven to 200°C.\n2. Toss squash and onions with olive oil, salt and pepper. Spread in a large roasting tin.\n3. Nestle sausages among the vegetables. Tuck in garlic cloves and rosemary sprigs.\n4. Roast 40 mins, turning once halfway through, until sausages are golden and squash is caramelised.',
                 seasonal_tag='Autumn/Winter', storage_guidance='Leftovers keep 2 days in fridge.'),
            dict(producer=p2, title='Cheddar & Apple Chutney Open Sandwich',
                 description='The classic British combination — sharp cheddar and spiced chutney on good bread.',
                 ingredients='2 slices Wholemeal Bread\n80g Mature Cheddar Cheese, thickly sliced\n2 tbsp Apple Chutney\nA few leaves of watercress or rocket\nBlack pepper',
                 instructions='1. Toast the wholemeal bread if you like, or serve fresh.\n2. Lay thick slices of cheddar over the bread.\n3. Spoon chutney generously alongside or on top.\n4. Add a handful of watercress leaves and a grind of black pepper.\n5. Serve open or press together as a sandwich.',
                 seasonal_tag='All Year', storage_guidance='Assemble and eat straight away.'),
            dict(producer=p2, title='Beef Mince & Spinach Pasta Sauce',
                 description='A quick, nutritious weeknight bolognese-style sauce using good-quality local beef.',
                 ingredients='500g Beef Mince\n150g Baby Spinach\n400g tinned tomatoes\n1 onion, diced\n3 garlic cloves, minced\n1 tbsp olive oil\n1 tsp dried oregano\nSalt and pepper\n400g pasta to serve',
                 instructions='1. Cook pasta according to packet instructions.\n2. Fry onion in olive oil 8 mins until soft. Add garlic and oregano, cook 1 min.\n3. Add beef mince, breaking it up with a spoon. Brown all over, 8 mins.\n4. Add tinned tomatoes, season, and simmer 15 mins.\n5. Stir in spinach until wilted — about 2 mins.\n6. Serve over pasta with grated cheddar if you like.',
                 seasonal_tag='All Year', storage_guidance='Sauce keeps 3 days in fridge or freeze for 3 months.'),
            dict(producer=p2, title='Strawberries with Yoghurt and Raspberry Jam',
                 description='Summer in a bowl. The easiest, most satisfying dessert when the fruit is good.',
                 ingredients='250g Strawberries, hulled and halved\n150g Natural Yoghurt\n2 tbsp Raspberry Jam\nFresh mint to serve (optional)',
                 instructions='1. Arrange strawberries in bowls.\n2. Spoon yoghurt generously alongside.\n3. Warm the raspberry jam slightly so it becomes a loose sauce, then drizzle over.\n4. Scatter with a few mint leaves if using.\n5. Eat immediately while the strawberries are at room temperature.',
                 seasonal_tag='Summer', storage_guidance='Eat fresh — do not make in advance.'),
            dict(producer=p2, title='Lamb Chops with Asparagus and Lemon',
                 description='A beautifully simple spring supper. Good lamb and fresh asparagus need very little.',
                 ingredients='1 pack Lamb Chops (2 chops)\n1 bunch Fresh Asparagus, woody ends snapped off\n2 tbsp olive oil\nJuice and zest of 1 lemon\n2 garlic cloves, crushed\nFresh thyme from herb bundle\nSalt and pepper',
                 instructions='1. Marinate chops 20 mins in olive oil, garlic, thyme, lemon zest, salt and pepper.\n2. Heat a griddle or frying pan until very hot.\n3. Cook chops 3–4 mins per side for medium. Rest 5 mins.\n4. Meanwhile, toss asparagus in olive oil, salt and pepper. Griddle 3–4 mins, turning.\n5. Arrange chops and asparagus on a plate. Squeeze over lemon juice.',
                 seasonal_tag='Spring', storage_guidance='Eat immediately.'),
            dict(producer=p2, title='Cox Apple & Pear Crumble',
                 description='The most comforting autumn pudding. Our heritage orchard fruit baked under a buttery oat crumble.',
                 ingredients='3 Cox Apples, peeled, cored and sliced\n2 Conference Pears, peeled, cored and sliced\n3 tbsp caster sugar\n1 tsp cinnamon\n\nFor the crumble:\n180g plain flour\n90g cold butter, cubed\n80g rolled oats\n80g demerara sugar\nPinch of salt',
                 instructions='1. Preheat oven to 180°C.\n2. Toss apples and pears with caster sugar and cinnamon. Spread in a baking dish.\n3. Rub flour and cold butter together until the mixture resembles breadcrumbs. Stir in oats, demerara sugar and salt.\n4. Scatter crumble mixture evenly over the fruit.\n5. Bake 35–40 mins until golden and bubbling at the edges.\n6. Serve warm with yoghurt or cream.',
                 seasonal_tag='Autumn', storage_guidance='Keeps in fridge 3 days. Reheat in oven at 170°C for 15 mins.'),
        ]

        created_recipes = 0
        for data in RECIPES:
            if not Recipe.objects.filter(title=data['title']).exists():
                Recipe.objects.create(**data)
                created_recipes += 1
        self.stdout.write(f'  [+] Created {created_recipes} recipes')

        # ── Farm Stories ──────────────────────────────────────────────────────
        STORIES = [
            dict(producer=p1, title='The Spring Awakening: What Happens on the Farm in April',
                 content='April is the most exhausting and exciting month at Bristol Valley Farm. After a long, muddy winter the whole farm seems to shake itself awake at once.\n\nThe polytunnel is already bursting — trays of cavolo nero and chard seedlings jostling for space, waiting for the soil temperature outside to creep above 10°C. The hens have noticed the lengthening days too. Egg production has jumped almost overnight from 3 dozen to nearly 9 dozen a day.\n\nOur small orchard is a cloud of white blossom right now. The Cox and Bramley trees are a good two weeks ahead of last year, which hopefully signals a decent harvest in October.\n\nThe bees are flying strongly and the first flush of dandelion is giving them plenty of early forage. This is the time of year we live for.'),
            dict(producer=p1, title='Why We Switched to No-Dig Farming',
                 content='Three years ago we made the decision to stop ploughing our market garden beds. It felt terrifying — we had been tilling for twenty years.\n\nConventional tillage destroys the mycelial networks that plants use to communicate and share nutrients. Every time you plough, you are essentially burning the internet.\n\nThe no-dig method involves laying thick cardboard over weeds, topping with 10–15cm of well-aged compost, and planting directly into that. Our results after three years: weed pressure is down by 70%. Soil structure has improved dramatically. And our crops taste different — more flavourful. Several restaurant customers have noticed unprompted.\n\nWe buy 20 tonnes of compost from a local food-waste processor each year. Food waste becoming soil becoming food again.'),
            dict(producer=p1, title='Meet Our Saddleback Pigs',
                 content='We only keep four Saddleback pigs at a time — they arrive as weaners in early spring and go to the butcher in late autumn. A short life, but a genuinely good one.\n\nBritish Saddlebacks are a rare breed with beautiful black-and-white markings. They spend their days rooting in a half-acre paddock, with a deep-straw ark for shelter. We feed them on organic pig nuts, surplus vegetables, and dairy waste. No hormones, no antibiotics.\n\nThe meat is extraordinary — deeply flavoured, well-marbled. Our pork and fennel sausages are made by a small butcher in Bedminster we have worked with for a decade.\n\nWe will not pretend it is not difficult on the day they leave. But we are proud of how they lived.'),
            dict(producer=p1, title='Foraging Along the Avon: Our Wild Garlic Season',
                 content='Every April without fail, the woodlands along the Avon Gorge fill with the unmistakeable scent of wild garlic. It is one of the great British seasonal pleasures.\n\nWe follow a strict rule: never take more than a third of any patch, and never from the same spot two years running. We only pick the leaves, never the flowers.\n\nAfter picking, the leaves are washed three times in cold water, then blended the same day with cold-pressed olive oil, pine nuts and aged Parmesan.\n\nThe season lasts roughly four weeks. Once it is gone, it is gone. If you see it on the marketplace, do not sleep on it.'),
            dict(producer=p1, title='A Terrible Frost and What It Taught Us',
                 content='On the 3rd of May two years ago, Bristol had its latest killing frost in living memory. We lost an estimated £4,000 worth of crops overnight.\n\nThe cavolo nero seedlings we had just transplanted were gone. The young courgette plants were black by morning. It was one of the most demoralising mornings in 22 years of farming.\n\nBut it taught us things we needed to learn. We now run a phased planting system: 30% of any crop goes out at the normal time, the remaining 70% in two later batches. We have also invested in floating row cover.\n\nThe frost did not break us. It made us more resilient.'),
            dict(producer=p2, title='The Art of the Drinking Shrub',
                 content='A shrub — in the culinary sense — is a vinegar-based drinking syrup. The word comes from the Arabic sharab, meaning drink. They were hugely popular in 17th and 18th century Britain as a way of preserving summer fruit.\n\nOur hedgerow shrub starts with blackberries and rosehips foraged from hedgerows around the smallholding. We macerate the fruit with raw cane sugar for 48 hours, then strain and combine with raw apple cider vinegar from Somerset. The mixture sits in stoneware crocks for a further two weeks to mellow.\n\nMixed with sparkling water it makes a genuinely sophisticated non-alcoholic drink. It also makes an extraordinary salad dressing.\n\nWe are committed to making drinks that feel as special as wine.'),
            dict(producer=p2, title='Why We Became Certified Organic — And Why It Matters',
                 content='Getting our Soil Association certification took three years of paperwork, inspections and detailed record-keeping. We questioned ourselves many times.\n\nWe had been farming without synthetic chemicals for nearly a decade before we applied — so in practice very little changed. What the certification gave us was accountability.\n\nThe UK organic standards require detailed records of everything that goes onto the land. No synthetic herbicides, pesticides or artificial fertilisers. Our livestock must have genuine outdoor access.\n\nWe believe this matters beyond the health benefits. Industrial agriculture is one of the leading causes of soil degradation and biodiversity loss in Britain. By farming organically and selling direct, we are part of a different food system — one that takes the long view.'),
            dict(producer=p2, title='Quince: The Most Overlooked Fruit in Britain',
                 content='Every autumn we fight a quiet battle against the quince\'s terrible reputation. Most people have never tasted one. Some vaguely recall that you cannot eat them raw. And so they get overlooked while customers reach past them for apples.\n\nThis is a tragedy.\n\nCooked, the quince transforms. It turns from pale yellow to a spectacular deep coral-pink. Its astringency melts away and it becomes intensely aromatic — like a rose-scented pear with something almost tropical underneath. Turned into membrillo, it keeps for three months and is the greatest companion any cheese has ever had.\n\nOur trees are forty years old. In a good year each gives over 30kg of fruit. Please: try a quince this autumn.'),
            dict(producer=p2, title='How We Source Our Cheese Cultures',
                 content='Making goats cheese is a lesson in patience and microbiology. The character of the cheese is largely determined by the cultures you use and the milk you start with.\n\nOur goats are Anglo-Nubian cross, chosen for their rich, high-fat milk. We milk twice a day and make cheese within 6 hours of the morning milking.\n\nThe starter culture is a blend of mesophilic bacteria we have maintained ourselves for eleven years, refreshing it weekly. Cultures age and mellow like sourdough starters. Ours has a particular clean, slightly citrusy character.\n\nAfter culturing, the curd is gently ladled into cylindrical moulds lined with fine cloth. The whey drains for 24 hours, then the cheese is unmoulded, dusted with vegetable ash, and left to develop for 3–5 days.'),
            dict(producer=p2, title='Making Elderflower & Gooseberry Jelly',
                 content='Elderflower and gooseberry share one of nature\'s more remarkable flavour coincidences: both contain the same aromatic compound that gives muscatel grapes their characteristic scent. Pair them together and the result is something that tastes almost impossibly floral.\n\nWe pick our elderflower heads in late May and early June, always in the early morning before the sun fades the volatile aromatics. The heads go into a large pot with lemon zest and citric acid, steeping for 24 hours.\n\nThe gooseberries are cooked down to a pulp and strained through muslin overnight. The two liquids are combined, sugar added, and brought to a setting point of 105°C.\n\nIt is, without question, our most popular product.'),
        ]

        created_stories = 0
        for data in STORIES:
            if not FarmStory.objects.filter(title=data['title']).exists():
                FarmStory.objects.create(**data)
                created_stories += 1
        self.stdout.write(f'  [+] Created {created_stories} farm stories')

        self.stdout.write(self.style.SUCCESS('\n✓ Seed complete!\n'))
        self.stdout.write('Login credentials:')
        self.stdout.write('  producer1   / TestPass123!')
        self.stdout.write('  producer2   / TestPass123!')
        self.stdout.write('  customer1   / TestPass123!')
        self.stdout.write('  restaurant1 / TestPass123!')
        self.stdout.write('  community1  / TestPass123!')
        self.stdout.write('  admin       / Admin123!')
