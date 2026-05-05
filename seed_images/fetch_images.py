# Run with: py fetch_images.py
# Images saved to seed_images/products/
# Then run: docker compose exec web python manage.py load_images

import os
import time
import requests

SAVE_DIR = os.path.join(os.path.dirname(__file__), 'products')
os.makedirs(SAVE_DIR, exist_ok=True)

# Wikipedia article title for each product image
ITEMS = {
    'carrots.jpg':            'Carrot',
    'spinach.jpg':            'Spinach',
    'hen_eggs.jpg':           'Egg_(food)',
    'whole_milk.jpg':         'Milk',
    'cheddar.jpg':            'Cheddar_cheese',
    'yoghurt.jpg':            'Yogurt',
    'sourdough.jpg':          'Sourdough',
    'strawberry_jam.jpg':     'Strawberry_jam',
    'raspberry_jam.jpg':      'Raspberry',
    'lemon_curd.jpg':         'Lemon_curd',
    'apple_chutney.jpg':      'Chutney',
    'asparagus.jpg':          'Asparagus',
    'fresh_herbs.jpg':        'Herb',
    'whole_chicken.jpg':      'Chicken_(food)',
    'sausages.jpg':           'Sausage',
    'beef_mince.jpg':         'Ground_beef',
    'strawberries.jpg':       'Strawberry',
    'raspberries.jpg':        'Raspberry',
    'apples.jpg':             'Cox_apple',
    'pears.jpg':              'Conference_pear',
    'apple_juice.jpg':        'Apple_juice',
    'elderflower_cordial.jpg':'Elderflower_cordial',
    'lemonade.jpg':           'Lemonade',
}

WIKI_HEADERS = {
    'User-Agent': 'BristolFoodNetworkScript/1.0 (local setup)',
    'Accept': 'application/json',
}
IMG_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'Accept': 'image/jpeg,image/png,image/*',
    'Referer': 'https://en.wikipedia.org/',
}

ok, failed = 0, []

for filename, article in ITEMS.items():
    dest = os.path.join(SAVE_DIR, filename)

    # Skip if already downloaded
    if os.path.isfile(dest) and os.path.getsize(dest) > 5000:
        print(f'  [skip] {filename} already exists')
        ok += 1
        continue

    # Step 1: get image URL from Wikipedia summary API
    img_url = None
    try:
        r = requests.get(
            f'https://en.wikipedia.org/api/rest_v1/page/summary/{article}',
            headers=WIKI_HEADERS, timeout=15
        )
        if r.status_code == 200:
            data = r.json()
            img_url = (data.get('originalimage') or data.get('thumbnail') or {}).get('source')
    except Exception as e:
        print(f'  [api error] {filename}: {e}')

    if not img_url:
        print(f'  [no image] {filename} — article: {article}')
        failed.append(filename)
        time.sleep(1)
        continue

    # Step 2: download the image
    time.sleep(1.5)  # be polite — avoids rate limiting
    try:
        r = requests.get(img_url, headers=IMG_HEADERS, timeout=30)
        if r.status_code == 200 and len(r.content) > 5000:
            with open(dest, 'wb') as f:
                f.write(r.content)
            print(f'  [ok] {filename}  ({len(r.content) // 1024} KB)')
            ok += 1
        else:
            print(f'  [fail] {filename}  HTTP {r.status_code}')
            failed.append(filename)
    except Exception as e:
        print(f'  [error] {filename}: {e}')
        failed.append(filename)

    time.sleep(0.5)

print(f'\nDone: {ok}/{len(ITEMS)} downloaded.')
if failed:
    print(f'Missing: {", ".join(failed)}')
    print('For any missing ones, drop the image manually into seed_images/products/')
