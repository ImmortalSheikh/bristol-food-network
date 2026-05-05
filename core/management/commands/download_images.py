import os
import time
import requests
from django.core.management.base import BaseCommand
from django.conf import settings
from core.models import Product

# Maps each product name to:
#   (local filename, Wikipedia article title, fallback article title)
# The Wikipedia REST API returns the main image for each article — always accurate.
PRODUCT_ARTICLES = {
    'Organic Carrots':          ('carrots.jpg',           'Carrot',              'Carrot'),
    'Baby Spinach':             ('spinach.jpg',           'Spinach',             'Spinach'),
    'Cherry Tomatoes':          ('cherry_tomatoes.jpg',   'Cherry_tomato',       'Tomato'),
    'New Potatoes':             ('potatoes.jpg',          'Potato',              'Potato'),
    'Free-Range Hen Eggs':      ('hen_eggs.jpg',          'Egg_(food)',          'Chicken_egg'),
    'Whole Milk':               ('whole_milk.jpg',        'Milk',                'Milk'),
    'Mature Cheddar Cheese':    ('cheddar.jpg',           'Cheddar_cheese',      'Cheese'),
    'Natural Yoghurt':          ('yoghurt.jpg',           'Yogurt',              'Yogurt'),
    'Sourdough Loaf':           ('sourdough.jpg',         'Sourdough',           'Sourdough_bread'),
    'Wholemeal Bread':          ('wholemeal.jpg',         'Brown_bread',         'Bread'),
    'Butter Croissants':        ('croissants.jpg',        'Croissant',           'Croissant'),
    'Cinnamon Rolls':           ('cinnamon_rolls.jpg',    'Cinnamon_roll',       'Cinnamon_roll'),
    'Strawberry Jam':           ('strawberry_jam.jpg',    'Strawberry_jam',      'Fruit_preserves'),
    'Raspberry Jam':            ('raspberry_jam.jpg',     'Raspberry',           'Fruit_preserves'),
    'Lemon Curd':               ('lemon_curd.jpg',        'Lemon_curd',          'Lemon'),
    'Apple Chutney':            ('apple_chutney.jpg',     'Chutney',             'Apple'),
    'Fresh Asparagus':          ('asparagus.jpg',         'Asparagus',           'Asparagus'),
    'Butternut Squash':         ('butternut_squash.jpg',  'Butternut_squash',    'Squash_(plant)'),
    'Mixed Wild Mushrooms':     ('mushrooms.jpg',         'Chanterelle',         'Mushroom'),
    'Fresh Herb Bundle':        ('fresh_herbs.jpg',       'Herb',                'Thyme'),
    'Whole Free-Range Chicken': ('whole_chicken.jpg',     'Chicken_(food)',      'Roast_chicken'),
    'Pork Sausages':            ('sausages.jpg',          'Sausage',             'Pork'),
    'Beef Mince':               ('beef_mince.jpg',        'Ground_beef',         'Beef'),
    'Lamb Chops':               ('lamb_chops.jpg',        'Lamb_and_mutton',     'Lamb_chop'),
    'Strawberries':             ('strawberries.jpg',      'Strawberry',          'Strawberry'),
    'Raspberries':              ('raspberries.jpg',       'Raspberry',           'Raspberry'),
    'Cox Apples':               ('apples.jpg',            'Cox_apple',           'Apple'),
    'Conference Pears':         ('pears.jpg',             'Conference_pear',     'Pear'),
    'Fresh Apple Juice':        ('apple_juice.jpg',       'Apple_juice',         'Apple_cider'),
    'Elderflower Cordial':      ('elderflower_cordial.jpg', 'Elderflower_cordial', 'Elderflower'),
    'Blackcurrant Juice':       ('blackcurrant_juice.jpg', 'Blackcurrant',       'Blackcurrant'),
    'Fresh Lemonade':           ('lemonade.jpg',          'Lemonade',            'Lemonade'),
}

HEADERS = {
    'User-Agent': 'BristolFoodNetwork/1.0 (educational project; contact@example.com)',
    'Accept': 'application/json',
}

IMG_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; BristolFoodNetworkBot/1.0)',
    'Accept': 'image/jpeg,image/png,image/webp,image/*',
    'Referer': 'https://en.wikipedia.org/',
}


def get_wikipedia_image_url(article_title):
    """Fetch the main thumbnail image URL for a Wikipedia article using the REST summary API."""
    url = f'https://en.wikipedia.org/api/rest_v1/page/summary/{article_title}'
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            # Prefer original high-res image, fall back to thumbnail
            orig = data.get('originalimage', {})
            thumb = data.get('thumbnail', {})
            img_url = orig.get('source') or thumb.get('source')
            if img_url:
                return img_url
    except Exception:
        pass
    return None


class Command(BaseCommand):
    help = 'Download accurate food photos from Wikipedia for all products.'

    def handle(self, *args, **options):
        media_root = str(settings.MEDIA_ROOT)
        products_dir = os.path.join(media_root, 'products')
        os.makedirs(products_dir, exist_ok=True)

        self.stdout.write(self.style.NOTICE('\nFetching food photos from Wikipedia...\n'))

        ok, failed = 0, []

        for product_name, (filename, article, fallback) in PRODUCT_ARTICLES.items():
            filepath = os.path.join(products_dir, filename)
            img_url = None

            # Try primary article
            img_url = get_wikipedia_image_url(article)

            # Try fallback article if primary had no image
            if not img_url and fallback != article:
                img_url = get_wikipedia_image_url(fallback)
                if img_url:
                    self.stdout.write(f'  [fallback] {product_name} → {fallback}')

            if not img_url:
                failed.append(product_name)
                self.stdout.write(self.style.WARNING(f'  [no image] {product_name}'))
                time.sleep(0.3)
                continue

            # Download the image
            try:
                resp = requests.get(img_url, headers=IMG_HEADERS, timeout=30, stream=True)
                if resp.status_code == 200:
                    content = resp.content
                    if len(content) > 3000:
                        with open(filepath, 'wb') as f:
                            f.write(content)
                        Product.objects.filter(name=product_name).update(
                            image=f'products/{filename}'
                        )
                        ok += 1
                        self.stdout.write(
                            f'  [ok] {product_name}  ({len(content) // 1024} KB)'
                        )
                    else:
                        failed.append(product_name)
                        self.stdout.write(self.style.WARNING(
                            f'  [tiny] {product_name}  ({len(content)} bytes — skipped)'
                        ))
                else:
                    failed.append(product_name)
                    self.stdout.write(self.style.WARNING(
                        f'  [fail] {product_name}  HTTP {resp.status_code}'
                    ))
            except Exception as e:
                failed.append(product_name)
                self.stdout.write(self.style.ERROR(f'  [error] {product_name} — {e}'))

            time.sleep(0.4)

        self.stdout.write('')
        if not failed:
            self.stdout.write(self.style.SUCCESS(f'✓ All {ok} images downloaded!'))
        else:
            self.stdout.write(self.style.WARNING(
                f'Got {ok}/{len(PRODUCT_ARTICLES)}.'
            ))
            if failed:
                self.stdout.write(f'Missing: {", ".join(failed)}')
