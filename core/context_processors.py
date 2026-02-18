from .models import Cart


def cart_count(request):
    """Makes cart item count available in all templates"""
    if request.user.is_authenticated and not request.user.is_producer():
        try:
            cart = Cart.objects.get(customer=request.user)
            return {'cart_count': cart.item_count}
        except Cart.DoesNotExist:
            pass
    return {'cart_count': 0}