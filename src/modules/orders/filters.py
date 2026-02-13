import django_filters

from modules.orders.models import Order


class OrderFilter(django_filters.FilterSet):
    status = django_filters.CharFilter(field_name="status", lookup_expr="iexact")
    customer = django_filters.UUIDFilter(field_name="customer_id")
    start_date = django_filters.DateFilter(field_name="created_at", lookup_expr="gte")
    end_date = django_filters.DateFilter(field_name="created_at", lookup_expr="lte")
    min_total = django_filters.NumberFilter(
        field_name="total_amount", lookup_expr="gte"
    )
    max_total = django_filters.NumberFilter(
        field_name="total_amount", lookup_expr="lte"
    )

    class Meta:
        model = Order
        fields = [
            "status",
            "customer",
            "start_date",
            "end_date",
            "min_total",
            "max_total",
        ]
