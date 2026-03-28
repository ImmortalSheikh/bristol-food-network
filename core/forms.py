from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import User, ProducerProfile, CustomerProfile, Product, ProductAllergen, ALLERGEN_CHOICES


# ─────────────────────────────────────────────────────────────
# REGISTRATION FORMS
# ─────────────────────────────────────────────────────────────

class ProducerRegistrationForm(UserCreationForm):
    """TC-001: Producer account registration"""
    business_name = forms.CharField(max_length=200, label='Business / Farm Name')
    contact_name = forms.CharField(max_length=100, label='Contact Name')
    phone = forms.CharField(max_length=20, label='Phone Number')
    farm_address = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        label='Farm Address'
    )
    farm_postcode = forms.CharField(max_length=10, label='Farm Postcode')
    description = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False,
        label='About your farm (optional)'
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Style all fields with Bootstrap
        for field in self.fields.values():
            if not isinstance(field.widget, forms.Textarea):
                field.widget.attrs['class'] = 'form-control'
            else:
                field.widget.attrs['class'] = 'form-control'

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'producer'
        user.phone = self.cleaned_data['phone']
        if commit:
            user.save()
            ProducerProfile.objects.create(
                user=user,
                business_name=self.cleaned_data['business_name'],
                contact_name=self.cleaned_data['contact_name'],
                farm_address=self.cleaned_data['farm_address'],
                farm_postcode=self.cleaned_data['farm_postcode'],
                description=self.cleaned_data.get('description', ''),
            )
        return user


class CustomerRegistrationForm(UserCreationForm):
    """TC-002: Customer account registration"""
    CUSTOMER_TYPE_CHOICES = [
        ('individual', 'Individual / Family'),
        ('community_group', 'Community Group / School / Charity'),
        ('restaurant', 'Restaurant / Cafe'),
    ]

    full_name = forms.CharField(max_length=200, label='Full Name')
    email = forms.EmailField(required=True)
    phone = forms.CharField(max_length=20, label='Phone Number')
    customer_type = forms.ChoiceField(
        choices=CUSTOMER_TYPE_CHOICES,
        label='Account Type'
    )
    organisation_name = forms.CharField(
        max_length=200, required=False,
        label='Organisation Name',
        help_text='Required for community groups and restaurants'
    )
    delivery_address = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        label='Delivery Address'
    )
    delivery_postcode = forms.CharField(max_length=10, label='Delivery Postcode')
    terms = forms.BooleanField(
        required=True,
        label='I accept the terms and conditions'
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name == 'terms':
                field.widget.attrs['class'] = 'form-check-input'
            elif isinstance(field.widget, forms.Textarea):
                field.widget.attrs['class'] = 'form-control'
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'

    def clean(self):
        cleaned = super().clean()
        customer_type = cleaned.get('customer_type')
        organisation_name = cleaned.get('organisation_name', '').strip()
        if customer_type in ('community_group', 'restaurant') and not organisation_name:
            raise ValidationError(
                'Organisation name is required for community groups and restaurants.'
            )
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        customer_type = self.cleaned_data['customer_type']
        user.role = customer_type if customer_type != 'individual' else 'customer'
        user.phone = self.cleaned_data['phone']
        user.email = self.cleaned_data['email']
        # Split full name into first/last
        parts = self.cleaned_data['full_name'].split(' ', 1)
        user.first_name = parts[0]
        user.last_name = parts[1] if len(parts) > 1 else ''
        if commit:
            user.save()
            CustomerProfile.objects.create(
                user=user,
                customer_type=customer_type,
                organisation_name=self.cleaned_data.get('organisation_name', ''),
                delivery_address=self.cleaned_data['delivery_address'],
                delivery_postcode=self.cleaned_data['delivery_postcode'],
            )
        return user


class LoginForm(AuthenticationForm):
    """Custom login form with Bootstrap styling"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Username',
            'autofocus': True,
        })
        self.fields['password'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Password',
        })


# ─────────────────────────────────────────────────────────────
# PRODUCT FORM
# ─────────────────────────────────────────────────────────────

class ProductForm(forms.ModelForm):
    """TC-003 / TC-011: Create and edit product listings"""
    allergens = forms.MultipleChoiceField(
        choices=ALLERGEN_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label='Allergens — tick all that apply (UK 14 major allergens)'
    )

    class Meta:
        model = Product
        fields = [
            'name', 'category', 'description', 'price', 'unit',
            'stock_quantity', 'low_stock_threshold', 'availability',
            'is_organic', 'harvest_date', 'best_before_date',
            'season_start_month', 'season_end_month', 'image',
            'is_surplus', 'surplus_discount_percent', 'surplus_expiry',
        ]
        widgets = {
            'harvest_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
            }),
            'best_before_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
                'min': timezone.now().date().isoformat(),
            }),
            'surplus_expiry': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-control',
            }),
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        instance = kwargs.get('instance')
        super().__init__(*args, **kwargs)

        # Always set min to today so it stays current on each page load
        self.fields['best_before_date'].widget.attrs['min'] = timezone.now().date().isoformat()

        # Pre-populate allergens if editing
        if instance:
            current = list(instance.product_allergens.values_list('allergen', flat=True))
            self.fields['allergens'].initial = current

        # Bootstrap styling
        for name, field in self.fields.items():
            if name == 'allergens':
                continue
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'form-check-input'
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = 'form-select'
            elif not isinstance(field.widget, (forms.Textarea, forms.DateInput, forms.DateTimeInput)):
                field.widget.attrs['class'] = 'form-control'

    def clean_best_before_date(self):
        """Server-side validation as a backup to the HTML min attribute"""
        date = self.cleaned_data.get('best_before_date')
        if date and date < timezone.now().date():
            raise ValidationError('Best before date cannot be in the past.')
        return date

    def save_allergens(self, product):
        """Save allergen selections — call this after product.save()"""
        product.product_allergens.all().delete()
        for allergen in self.cleaned_data.get('allergens', []):
            ProductAllergen.objects.create(product=product, allergen=allergen)


# ─────────────────────────────────────────────────────────────
# CART FORM
# ─────────────────────────────────────────────────────────────

class CartItemForm(forms.Form):
    quantity = forms.DecimalField(
        min_value=0.01,
        decimal_places=2,
        max_digits=10,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '0.1',
            'step': '0.1',
            'style': 'width:100px',
        })
    )

class RecurringOrderForm(forms.ModelForm):
    """TC-018: Create / edit a recurring order template"""
    class Meta:
        from .models import RecurringOrder
        model  = RecurringOrder
        fields = ['name', 'order_day', 'delivery_day',
                  'delivery_address', 'delivery_postcode', 'special_instructions']
        widgets = {
            'delivery_address':      forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'special_instructions':  forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = 'form-select'
            elif not isinstance(field.widget, forms.Textarea):
                field.widget.attrs['class'] = 'form-control'