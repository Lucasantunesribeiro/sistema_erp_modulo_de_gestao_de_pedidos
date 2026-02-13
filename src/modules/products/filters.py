import django_filters

from modules.products.models import Product


class ProductFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(field_name="name", lookup_expr="icontains")
    sku = django_filters.CharFilter(field_name="sku", lookup_expr="iexact")
    min_price = django_filters.NumberFilter(field_name="price", lookup_expr="gte")
    max_price = django_filters.NumberFilter(field_name="price", lookup_expr="lte")
    active = django_filters.CharFilter(field_name="status", lookup_expr="iexact")

    class Meta:
        model = Product
        fields = ["name", "sku", "min_price", "max_price", "active"]
