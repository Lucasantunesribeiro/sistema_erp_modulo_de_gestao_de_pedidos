import django_filters

from modules.orders.models import Order


class OrderFilter(django_filters.FilterSet):
    status = django_filters.CharFilter(field_name="status", lookup_expr="iexact")
    customer_id = django_filters.UUIDFilter(field_name="customer_id")
    customer = django_filters.UUIDFilter(field_name="customer_id")
    date_min = django_filters.IsoDateTimeFilter(
        field_name="created_at", lookup_expr="gte"
    )
    date_max = django_filters.IsoDateTimeFilter(
        field_name="created_at", lookup_expr="lte"
    )
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
            "customer_id",
            "customer",
            "date_min",
            "date_max",
            "start_date",
            "end_date",
            "min_total",
            "max_total",
        ]
