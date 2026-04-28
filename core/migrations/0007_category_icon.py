# Adds an `icon` field to Category and backfills sensible defaults
# so every existing category gets a meaningful emoji.

from django.db import migrations, models


# Default emoji per known slug. Anything unknown falls back to 🛒.
DEFAULT_ICONS = {
    'vegetables': '🥦',
    'fruit': '🍓',
    'fruits': '🍓',
    'dairy': '🥛',
    'dairy-eggs': '🥛',
    'eggs': '🥚',
    'bakery': '🍞',
    'bread': '🍞',
    'meat': '🥩',
    'meat-poultry': '🍗',
    'poultry': '🍗',
    'fish': '🐟',
    'seafood': '🐟',
    'drinks': '🥤',
    'beverages': '🥤',
    'preserves': '🍯',
    'preserves-jams': '🍯',
    'jams': '🍯',
    'honey': '🍯',
    'seasonal': '🍂',
    'seasonal-specialties': '🍂',
    'herbs': '🌿',
    'spices': '🌶️',
    'pantry': '🥫',
    'snacks': '🍪',
    'sweets': '🍬',
    'cheese': '🧀',
}


def backfill_icons(apps, schema_editor):
    Category = apps.get_model('core', 'Category')
    for cat in Category.objects.all():
        slug = (cat.slug or '').lower()
        # exact match first, then prefix match (e.g. "dairy-eggs-something")
        icon = DEFAULT_ICONS.get(slug)
        if not icon:
            for key, value in DEFAULT_ICONS.items():
                if slug.startswith(key):
                    icon = value
                    break
        cat.icon = icon or '🛒'
        cat.save(update_fields=['icon'])


def noop_reverse(apps, schema_editor):
    # Nothing to undo; field will be dropped by the schema reversal.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_alter_cartitem_quantity_alter_orderitem_quantity_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='category',
            name='icon',
            field=models.CharField(
                default='🛒',
                max_length=8,
                help_text='Emoji or short symbol shown on cards. Always shows something.',
            ),
        ),
        migrations.RunPython(backfill_icons, noop_reverse),
    ]
