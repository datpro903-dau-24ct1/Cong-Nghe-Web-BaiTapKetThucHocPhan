from . import selectors


def nav_categories(request):
    """Đưa danh sách danh mục (đang có hàng) vào mọi template để dựng menu và chân trang."""
    return {"nav_categories": selectors.list_categories_with_products()}