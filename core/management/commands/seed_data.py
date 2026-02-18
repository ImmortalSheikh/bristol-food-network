from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import Category, ProducerProfile, CustomerProfile, Product

User = get_user_model()

CATEGORIES = [
    ('Vegetables', 'vegetables'),
    ('Dairy & Eggs', 'dairy-eggs'),
    ('Bakery', 'bakery'),
    ('Preserves & Jams', 'preserves-jams'),
    ('Seasonal Specialties', 'seasonal-specialties'),
    ('Meat & Poultry', 'meat-poultry'),
    ('Fruit', 'fruit'),
    ('Drinks', 'drinks'),
]


class Command(BaseCommand):
    help = 'Seed the database with initial categories and test data'

    def handle(self, *args, **options):
        # Create categories
        for name, slug in CATEGORIES:
            cat, created = Category.objects.get_or_create(slug=slug, defaults={'name': name})
            if created:
                self.stdout.write(f'  Created category: {name}')

        # Create test producer
        if not User.objects.filter(username='producer1').exists():
            producer_user = User.objects.create_user(
                username='producer1',
                email='jane.smith@bristolvalleyfarm.com',
                password='TestPass123!',
                role='producer',
                first_name='Jane',
                last_name='Smith',
                phone='01179 123456',
            )
            ProducerProfile.objects.create(
                user=producer_user,
                business_name='Bristol Valley Farm',
                contact_name='Jane Smith',
                farm_address='Valley Road, Bristol',
                farm_postcode='BS1 4DJ',
                description='Family farm growing seasonal vegetables and free range eggs.',
            )
            self.stdout.write('  Created test producer: producer1 / TestPass123!')

        # Create test customer
        if not User.objects.filter(username='customer1').exists():
            customer_user = User.objects.create_user(
                username='customer1',
                email='robert.johnson@email.com',
                password='TestPass123!',
                role='customer',
                first_name='Robert',
                last_name='Johnson',
                phone='07700 900123',
            )
            CustomerProfile.objects.create(
                user=customer_user,
                customer_type='individual',
                delivery_address='45 Park Street, Bristol',
                delivery_postcode='BS1 5JG',
            )
            self.stdout.write('  Created test customer: customer1 / TestPass123!')

        # Create sample products
        producer_profile = ProducerProfile.objects.filter(business_name='Bristol Valley Farm').first()
        if producer_profile and not Product.objects.filter(name='Organic Free Range Eggs').exists():
            veg_cat = Category.objects.get(slug='vegetables')
            dairy_cat = Category.objects.get(slug='dairy-eggs')

            Product.objects.create(
                producer=producer_profile,
                category=dairy_cat,
                name='Organic Free Range Eggs',
                description='Fresh organic eggs from free-range hens, collected daily',
                price=3.50,
                unit='dozen',
                stock_quantity=50,
                availability='in_season',
                is_organic=True,
            )
            Product.objects.create(
                producer=producer_profile,
                category=veg_cat,
                name='Organic Carrots',
                description='Fresh organic carrots, locally grown without pesticides',
                price=1.80,
                unit='kg',
                stock_quantity=100,
                availability='available',
                is_organic=True,
            )
            Product.objects.create(
                producer=producer_profile,
                category=veg_cat,
                name='Cherry Tomatoes',
                description='Sweet cherry tomatoes grown in our polytunnel',
                price=2.50,
                unit='kg',
                stock_quantity=30,
                availability='in_season',
                is_organic=False,
            )
            self.stdout.write('  Created sample products')

        # Create superuser
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser(
                username='admin',
                email='admin@bristolfoodnetwork.com',
                password='Admin123!',
                role='admin',
            )
            self.stdout.write('  Created superuser: admin / Admin123!')

        self.stdout.write(self.style.SUCCESS('\nSeed complete!'))
        self.stdout.write('\nTest accounts:')
        self.stdout.write('  Producer:  producer1 / TestPass123!')
        self.stdout.write('  Customer:  customer1 / TestPass123!')
        self.stdout.write('  Admin:     admin / Admin123!  (at /admin/)')