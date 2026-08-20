from .models import Category

def global_categories(request):
    """Provides all categories globally for navigation dropdowns."""
    try:
        categories = Category.objects.all().order_by('name')
    except Exception:
        categories = []
    return {
        'nav_categories': categories,
    }
