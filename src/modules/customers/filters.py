import django_filters

from modules.customers.models import Customer


class CustomerFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(field_name="name", lookup_expr="icontains")
    email = django_filters.CharFilter(field_name="email", lookup_expr="iexact")
    active = django_filters.BooleanFilter(field_name="is_active")

    class Meta:
        model = Customer
        fields = ["name", "email", "active"]
