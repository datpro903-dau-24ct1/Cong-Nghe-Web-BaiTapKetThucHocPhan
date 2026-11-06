"""Nơi lưu giỏ hàng. Services/selectors chỉ làm việc qua các store này, không biết request.

Một store cần có: quantities(), unit_prices(), set(product, quantity, *, refresh_price), remove(product_id).
"""
from django.db import transaction

from .models import Cart, CartItem

SESSION_KEY = "cart"


class SessionCartStore:
    """Giỏ của khách chưa đăng nhập: {"<mã sản phẩm>": số lượng} trong session, không lưu giá."""

    def __init__(self, session):
        self._session = session

    def quantities(self):
        """{product_id: số lượng}; bỏ qua mọi mục hỏng (session có thể bị sửa tay)."""
        raw = self._session.get(SESSION_KEY)
        if not isinstance(raw, dict):
            return {}
        result = {}
        for key, value in raw.items():
            try:
                product_id = int(key)
            except (TypeError, ValueError):
                continue
            if product_id < 1 or isinstance(value, bool) or not isinstance(value, int) or value < 1:
                continue
            result[product_id] = value
        return result

    def unit_prices(self):
        return {}

    def _save(self, quantities):
        # Gán lại cả dict để Django biết session đã thay đổi.
        self._session[SESSION_KEY] = {str(pid): qty for pid, qty in quantities.items()}

    def set(self, product, quantity, *, refresh_price):
        quantities = self.quantities()
        quantities[product.pk] = quantity
        self._save(quantities)

    def remove(self, product_id):
        quantities = self.quantities()
        quantities.pop(product_id, None)
        self._save(quantities)

    def clear(self):
        self._session.pop(SESSION_KEY, None)


class DbCartStore:
    """Giỏ của người dùng đã đăng nhập, lưu trong database kèm giá lúc thêm."""

    def __init__(self, user):
        self._user = user

    def _items(self):
        return CartItem.objects.filter(cart__user=self._user).order_by("id")

    def quantities(self):
        return dict(self._items().values_list("product_id", "quantity"))

    def unit_prices(self):
        return dict(self._items().values_list("product_id", "unit_price"))

    def set(self, product, quantity, *, refresh_price):
        with transaction.atomic():
            cart, _ = Cart.objects.get_or_create(user=self._user)
            item, created = CartItem.objects.get_or_create(
                cart=cart, product=product,
                defaults={"quantity": quantity, "unit_price": product.price},
            )
            if not created:
                item.quantity = quantity
                if refresh_price:
                    item.unit_price = product.price
                item.save()

    def remove(self, product_id):
        self._items().filter(product_id=product_id).delete()


def store_for_request(request):
    """Chọn nơi lưu giỏ theo trạng thái đăng nhập."""
    if request.user.is_authenticated:
        return DbCartStore(request.user)
    return SessionCartStore(request.session)
