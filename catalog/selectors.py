"""Các hàm đọc dữ liệu (không ghi)."""
from django.db.models import Case, IntegerField, Q, When

from .models import Category, Product


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