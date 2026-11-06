"""Các hàm đọc dữ liệu đơn hàng, mã giảm giá & thống kê dashboard (không ghi)."""
from collections import defaultdict
from datetime import date, datetime, time
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import F, Sum
from django.utils import timezone

from .models import Coupon, Order, OrderItem


def list_user_orders(user):
    """Danh sách đơn hàng của user (mới nhất trước), nạp sẵn các dòng chi tiết."""
    return (
        Order.objects.filter(user=user)
        .prefetch_related("items", "items__product")
        .order_by("-created_at", "-id")
    )


def get_user_order(user, order_id):
    """Đơn hàng theo mã nhưng chỉ khi thuộc về user; nạp sẵn các dòng sản phẩm."""
    return (
        Order.objects.filter(user=user, pk=order_id)
        .prefetch_related("items", "items__product")
        .first()
    )


def get_coupon_by_code(code):
    """Tìm mã giảm giá theo code (chuẩn hóa chữ in hoa); None nếu không có."""
    normalized = (code or "").strip().upper()
    if not normalized:
        return None
    return Coupon.objects.filter(code=normalized).first()


def _parse_date(value) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return date.fromisoformat(stripped)
        except ValueError:
            raise ValidationError("Ngày lọc không hợp lệ.", code="invalid_date")
    raise ValidationError("Ngày lọc không hợp lệ.", code="invalid_date")


def get_dashboard_stats(*, start_date=None, end_date=None, top_limit=5):
    """Thống kê doanh thu, số đơn, top sản phẩm bán chạy và đơn theo ngày (CN25)."""
    parsed_start = _parse_date(start_date)
    parsed_end = _parse_date(end_date)

    if parsed_start and parsed_end and parsed_start > parsed_end:
        raise ValidationError(
            "Ngày bắt đầu không được lớn hơn ngày kết thúc.",
            code="invalid_date_range",
        )

    tz = timezone.get_current_timezone()
    orders_qs = Order.objects.all()
    if parsed_start is not None:
        start_dt = timezone.make_aware(datetime.combine(parsed_start, time.min), tz)
        orders_qs = orders_qs.filter(created_at__gte=start_dt)
    if parsed_end is not None:
        end_dt = timezone.make_aware(datetime.combine(parsed_end, time.max), tz)
        orders_qs = orders_qs.filter(created_at__lte=end_dt)

    order_rows = list(
        orders_qs.values("id", "status", "total", "created_at").order_by("created_at", "id")
    )

    total_orders = len(order_rows)
    completed_orders = 0
    cancelled_orders = 0
    pending_orders = 0
    total_revenue = Decimal(0)
    daily_buckets = defaultdict(
        lambda: {"order_count": 0, "completed_count": 0, "revenue": Decimal(0)}
    )
    completed_order_ids = []

    for row in order_rows:
        status = row["status"]
        local_day = timezone.localtime(row["created_at"], tz).date()
        bucket = daily_buckets[local_day]
        bucket["order_count"] += 1

        if status == Order.Status.COMPLETED:
            completed_orders += 1
            completed_order_ids.append(row["id"])
            amount = row["total"] or Decimal(0)
            total_revenue += amount
            bucket["completed_count"] += 1
            bucket["revenue"] += amount
        elif status == Order.Status.CANCELLED:
            cancelled_orders += 1
        else:
            pending_orders += 1

    daily_orders = [
        {
            "date": day,
            "order_count": data["order_count"],
            "completed_count": data["completed_count"],
            "revenue": data["revenue"],
        }
        for day, data in sorted(daily_buckets.items(), key=lambda kv: kv[0])
    ]

    if completed_order_ids:
        top_qs = (
            OrderItem.objects.filter(order_id__in=completed_order_ids)
            .values("product_id", "product_name")
            .annotate(
                total_quantity=Sum("quantity"),
                total_amount=Sum(F("unit_price") * F("quantity")),
            )
            .order_by("-total_quantity", "-total_amount", "product_name")[:top_limit]
        )
        top_products = [
            {
                "product_id": item["product_id"],
                "product_name": item["product_name"],
                "total_quantity": item["total_quantity"] or 0,
                "total_amount": item["total_amount"] or Decimal(0),
            }
            for item in top_qs
        ]
    else:
        top_products = []

    return {
        "start_date": parsed_start,
        "end_date": parsed_end,
        "total_revenue": total_revenue,
        "total_orders": total_orders,
        "completed_orders": completed_orders,
        "pending_orders": pending_orders,
        "cancelled_orders": cancelled_orders,
        "top_products": top_products,
        "daily_orders": daily_orders,
    }
