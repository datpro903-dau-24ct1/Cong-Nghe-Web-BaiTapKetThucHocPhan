from . import selectors
from .stores import store_for_request


def cart_summary(request):
    """Đưa tổng số lượng trong giỏ vào mọi template để hiện trên header."""
    return {"cart_count": selectors.count_items(store_for_request(request))}
