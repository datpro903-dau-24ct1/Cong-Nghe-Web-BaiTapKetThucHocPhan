"""Các hàm đọc dữ liệu (không ghi)."""
from django.db.models import Case, IntegerField, Q, When

from .models import Category, Product, Review


def get_main_image(product):
    """Ảnh chính của sản phẩm; nếu chưa đặt thì lấy ảnh đầu tiên; None nếu chưa có ảnh."""
    return product.images.first()


def list_active_products(category=None):
    """Sản phẩm đang bán (mới nhất trước), nạp sẵn series/brand/ảnh để tránh truy vấn lặp."""
    products = (
        Product.objects.filter(is_active=True)
        .select_related("series", "brand")
        .prefetch_related("images")
    )
    if category is not None:
        products = products.filter(category=category)
    return products


def list_categories_with_products():
    """Chỉ các danh mục đang có ít nhất một sản phẩm đang bán (dùng cho menu)."""
    return Category.objects.filter(products__is_active=True).distinct()


def get_category_by_slug(slug):
    """Danh mục theo slug; None nếu không có."""
    return Category.objects.filter(slug=slug).first()


def get_active_product_by_slug(slug):
    """Sản phẩm đang bán theo slug; None nếu không có, đã ẩn hoặc đã xóa."""
    product = (
        Product.objects.filter(is_active=True, slug=slug)
        .select_related("category", "series", "brand")
        .prefetch_related("images")
        .first()
    )
    # MariaDB so sánh không phân biệt hoa/thường; so lại bằng Python để mọi CSDL cùng một kết quả.
    if product is None or product.slug != slug:
        return None
    return product


def list_related_products(product, limit=4):
    """Sản phẩm liên quan: cùng bộ anime lên trước, rồi cùng danh mục; bỏ chính nó và hàng đã ẩn."""
    return (
        Product.objects.filter(is_active=True)
        .filter(Q(series_id=product.series_id) | Q(category_id=product.category_id))
        .exclude(pk=product.pk)
        .annotate(
            same_series=Case(
                When(series_id=product.series_id, then=0),
                default=1,
                output_field=IntegerField(),
            )
        )
        .select_related("series", "brand")
        .prefetch_related("images")
        .order_by("same_series", "-created_at", "-id")[:limit]
    )


SORT_ORDERINGS = {
    "newest": ("-created_at", "-id"),
    "price_asc": ("price", "-created_at", "-id"),
    "price_desc": ("-price", "-created_at", "-id"),
    "name_asc": ("name", "-id"),
}


def list_scales():
    """Các tỉ lệ (1/7, 1/8...) đang có sản phẩm đang bán, sắp xếp theo tên."""
    return list(
        Product.objects.filter(is_active=True)
        .exclude(scale="")
        .values_list("scale", flat=True)
        .distinct()
        .order_by("scale")
    )


def search_products(
    category=None, *, q="", series=None, brand=None,
    price_min=None, price_max=None, scale="", sort="newest",
):
    """Tìm kiếm, lọc, sắp xếp sản phẩm đang bán. Tham số rỗng/None nghĩa là không lọc.

    Từ khóa dùng icontains (Django tự escape % và _); việc bỏ qua dấu tiếng Việt do
    collation utf8mb4_unicode_ci của MariaDB đảm nhiệm.
    """
    products = list_active_products(category)
    if q:
        products = products.filter(name__icontains=q)
    if series is not None:
        products = products.filter(series=series)
    if brand is not None:
        products = products.filter(brand=brand)
    if price_min is not None:
        products = products.filter(price__gte=price_min)
    if price_max is not None:
        products = products.filter(price__lte=price_max)
    if scale:
        products = products.filter(scale=scale)
    return products.order_by(*SORT_ORDERINGS.get(sort or "newest", SORT_ORDERINGS["newest"]))


def list_product_reviews(product):
    """Danh sách đánh giá của sản phẩm (mới nhất trước). Không truy vấn DB nếu review_count == 0."""
    if not getattr(product, "review_count", 0):
        return []
    return list(
        Review.objects.filter(product=product)
        .select_related("user")
        .order_by("-created_at", "-id")
    )


def has_purchased_product(user, product) -> bool:
    """Kiểm tra người dùng đã có đơn hàng (không bị hủy) chứa sản phẩm này chưa."""
    if user is None or not getattr(user, "is_authenticated", False) or product is None:
        return False
    from orders.models import Order, OrderItem

    return (
        OrderItem.objects.filter(order__user=user, product=product)
        .exclude(order__status=Order.Status.CANCELLED)
        .exists()
    )


def can_user_review_product(user, product) -> bool:
    """Người dùng được đánh giá khi đã đăng nhập, đã mua sản phẩm và chưa từng đánh giá."""
    if not has_purchased_product(user, product):
        return False
    if not getattr(product, "review_count", 0):
        return True
    return not Review.objects.filter(product=product, user=user).exists()
