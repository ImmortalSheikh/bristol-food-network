from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils.text import slugify
from decimal import Decimal

from core.models import Category, ProducerProfile, Product

User = get_user_model()


DEFAULT_CATEGORIES = [
    "Bakery",
    "Dairy & Eggs",
    "Drinks",
    "Fruit",
    "Meat & Poultry",
    "Preserves & Jams",
    "Seasonal Specialties",
    "Vegetables",
]


class Command(BaseCommand):
    help = "Seed the database with initial categories and optional demo producer/products."

    def add_arguments(self, parser):
        parser.add_argument(
            "--with-demo-products",
            action="store_true",
            help="Also create a demo producer + demo products (safe to re-run).",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding data..."))

        # 1) Categories
        for name in DEFAULT_CATEGORIES:
            slug = slugify(name)
            obj, created = Category.objects.get_or_create(
                slug=slug,
                defaults={"name": name, "description": ""},
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created category: {name}"))
            else:
                # keep name in sync in case someone edited it
                if obj.name != name:
                    obj.name = name
                    obj.save(update_fields=["name"])
                self.stdout.write(f"Category exists: {name}")

        if not options["with_demo_products"]:
            self.stdout.write(self.style.SUCCESS("Done (categories only)."))
            return

        # 2) Demo producer user
        demo_username = "producer1"
        demo_email = "demo_producer@example.com"
        demo_password = "FarmMan10!!"

        user, created = User.objects.get_or_create(
            username=demo_username,
            defaults={
                "email": demo_email,
                "role": "producer",
                "is_active": True,
            },
        )
        if created:
            user.set_password(demo_password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Created demo producer user: {demo_username}"))
        else:
            # ensure role is correct
            if getattr(user, "role", None) != "producer":
                user.role = "producer"
                user.save(update_fields=["role"])
            self.stdout.write(f"Demo producer user exists: {demo_username}")

        # 3) Producer profile
        profile, created = ProducerProfile.objects.get_or_create(
            user=user,
            defaults={
                "business_name": "Cardiff Farm",
                "contact_name": "Demo Producer",
                "farm_address": "1 Farm Road, Cardiff",
                "farm_postcode": "CF10 1AA",
                "description": "Demo producer profile seeded for development/testing.",
                "lead_time_hours": 48,
            },
        )
        if created:
            self.stdout.write(self.style.SUCCESS("Created ProducerProfile for demo producer."))
        else:
            self.stdout.write("ProducerProfile exists for demo producer.")

        # 4) Demo products (tied to categories + producer)
        demo_products = [
            # name, category, price, unit, stock
            ("Croissant", "Bakery", Decimal("3.50"), "each", Decimal("50")),
            ("Orange", "Fruit", Decimal("1.35"), "each", Decimal("100")),
            ("Cherry Tomatoes", "Vegetables", Decimal("2.50"), "pack", Decimal("30")),
        ]

        for name, cat_name, price, unit, stock in demo_products:
            cat = Category.objects.get(slug=slugify(cat_name))
            prod, created = Product.objects.get_or_create(
                producer=profile,
                name=name,
                defaults={
                    "category": cat,
                    "description": f"Seeded product: {name}",
                    "price": price,
                    "unit": unit,
                    "stock_quantity": stock,
                    "low_stock_threshold": Decimal("10"),
                    "availability": "available",
                    "is_organic": False,
                },
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created product: {name}"))
            else:
                # keep key fields in sync
                prod.category = cat
                prod.price = price
                prod.unit = unit
                prod.stock_quantity = stock
                prod.availability = "available"
                prod.save()
                self.stdout.write(f"Product exists/updated: {name}")

        self.stdout.write(self.style.SUCCESS("Done (categories + demo products)."))