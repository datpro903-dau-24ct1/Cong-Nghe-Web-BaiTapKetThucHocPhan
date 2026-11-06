"""Đọc dữ liệu giỏ hàng (không ghi)."""
from dataclasses import dataclass
from decimal import Decimal

from catalog.models import Product


@dataclass(frozen=True)
class CartLine:
    product: Product
    quantity: int
    unit_price: Decimal          # giá hiện tại của sản phẩm, luôn dùng để tính tiền
    old_price: Decimal | None    # giá lúc thêm vào giỏ, chỉ có khi giá đã đổi
    line_total: Decimal
    image: object                # ProductImage đầu tiên hoặc None
    available: bool              # có thể mua với số lượng hiện tại không
    problem: str                 # lý do không mua được ("" nếu available)

    @property
    def price_changed(self):
        return self.old_price is not None


def _check_availability(product, quantity):
    if not product.is_active:
        return "Sản phẩm không còn được bán."
    if product.stock == 0:
        return "Sản phẩm đã hết hàng."
    if quantity > product.stock:
        return f"Chỉ còn {product.stock} sản phẩm trong kho."
    return ""


def get_cart_lines(store):
    """Các dòng trong giỏ (thứ tự lúc thêm); bỏ dòng có sản phẩm đã bị xóa khỏi hệ thống."""
    quantities = store.quantities()
    if not quantities:
        return []
    recorded_prices = store.unit_prices()
    products = {
        p.pk: p
        for p in Product.objects.filter(pk__in=quantities)
        .select_related("series", "brand")
        .prefetch_related("images")
    }
    lines = []
    for product_id, quantity in quantities.items():
        product = products.get(product_id)
        if product is None:
            continue
        recorded = recorded_prices.get(product_id)
        images = list(product.images.all())
        problem = _check_availability(product, quantity)
        lines.append(CartLine(
            product=product,
            quantity=quantity,
            unit_price=product.price,
            old_price=recorded if recorded is not None and recorded != product.price else None,
            line_total=product.price * quantity,
            image=images[0] if images else None,
            available=not problem,
            problem=problem,
        ))
    return lines


def get_cart_total(lines):
    """Tổng tiền các dòng mua được; dòng hết hàng/bị ẩn/vượt tồn kho không được tính."""
    return sum((line.line_total for line in lines if line.available), Decimal(0))


def count_items(store):
    """Tổng số lượng sản phẩm trong giỏ (hiện ở header)."""
    return sum(store.quantities().values())
