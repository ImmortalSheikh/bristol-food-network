import os
import shutil
from django.core.management.base import BaseCommand
from django.conf import settings
from core.models import Product

# Maps product name → filename in seed_images/products/
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
    help = 'Load product images from seed_images/products/ into the media directory.'

    def handle(self, *args, **options):
        # Source: the seed_images folder inside the project (mounted at /app)
        source_dir = os.path.join('/app', 'seed_images', 'products')
        # Destination: the media volume
        media_root = str(settings.MEDIA_ROOT)
        dest_dir = os.path.join(media_root, 'products')
        os.makedirs(dest_dir, exist_ok=True)

        if not os.path.isdir(source_dir):
            self.stdout.write(self.style.ERROR(
                f'Source folder not found: {source_dir}\n'
                'Create seed_images/products/ in your project and drop images there.'
            ))
            return

        self.stdout.write(self.style.NOTICE(f'\nLoading images from {source_dir}...\n'))

        # Build a case-insensitive map of files in source_dir
        available = {f.lower(): f for f in os.listdir(source_dir)}

        ok, missing = 0, []

        for product_name, filename in PRODUCT_FILENAMES.items():
            dst = os.path.join(dest_dir, filename)

            # Find source file case-insensitively, also try .jpeg
            actual_name = available.get(filename.lower()) or available.get(filename.lower().replace('.jpg', '.jpeg'))
            if not actual_name:
                missing.append(f'{product_name} ({filename})')
                continue
            src = os.path.join(source_dir, actual_name)

            shutil.copy2(src, dst)
            Product.objects.filter(name=product_name).update(image=f'products/{filename}')
            ok += 1
            size_kb = os.path.getsize(dst) // 1024
            self.stdout.write(f'  [ok] {product_name}  ({size_kb} KB)')

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'✓ Loaded {ok} images.'))
        if missing:
            self.stdout.write(self.style.WARNING(
                f'Missing {len(missing)} images (Pillow placeholder used instead):'
            ))
            for m in missing:
                self.stdout.write(f'  - {m}')
