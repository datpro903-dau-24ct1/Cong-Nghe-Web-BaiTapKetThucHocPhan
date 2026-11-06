"""Nghiệp vụ giỏ hàng (ghi dữ liệu). Lỗi nghiệp vụ -> ValidationError(message, code=...)."""
import re

from django.core.exceptions import ValidationError
from django.db import transaction

from catalog.models import Product


def _parse_quantity(value):
    """Số nguyên từ 1 trở lên; chấp nhận int hoặc chuỗi chữ số, từ chối bool/float/rỗng."""
    if isinstance(value, str):
        value = value.strip()
        if re.fullmatch(r"[0-9]+", value):
            value = int(value)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValidationError("Số lượng phải là số nguyên từ 1 trở lên.", code="invalid_quantity")
    return value


def _get_sellable_product(product_id):
    product = Product.objects.filter(pk=product_id, is_active=True).first()
    if product is None:
        raise ValidationError("Sản phẩm không còn được bán.", code="product_unavailable")
    return product


def _check_stock(product, quantity):
    if product.stock == 0:
        raise ValidationError("Sản phẩm đã hết hàng.", code="out_of_stock")
    if quantity > product.stock:
        raise ValidationError(f"Chỉ còn {product.stock} sản phẩm trong kho.", code="exceeds_stock")


def add_item(store, product_id, quantity=1):
    """Thêm vào giỏ (cộng dồn nếu đã có) và ghi nhận giá hiện tại của sản phẩm."""
    quantity = _parse_quantity(quantity)
    with transaction.atomic():
        product = _get_sellable_product(product_id)
        new_quantity = store.quantities().get(product.pk, 0) + quantity
        _check_stock(product, new_quantity)
        store.set(product, new_quantity, refresh_price=True)


def set_quantity(store, product_id, quantity):
    """Đặt số lượng của một dòng đã có trong giỏ; giữ nguyên giá đã ghi nhận."""
    quantity = _parse_quantity(quantity)
    with transaction.atomic():
        if product_id not in store.quantities():
            raise ValidationError("Sản phẩm không có trong giỏ hàng.", code="not_in_cart")
        product = _get_sellable_product(product_id)
        _check_stock(product, quantity)
        store.set(product, quantity, refresh_price=False)


def remove_item(store, product_id):
    """Xóa một dòng khỏi giỏ; không có thì thôi (xóa hai lần không phải lỗi)."""
    store.remove(product_id)


def merge_carts(session_store, db_store):
    """Gộp giỏ session vào giỏ DB của user khi đăng nhập/đăng ký (CN10).

    Trả về danh sách thông báo cảnh báo nếu có sản phẩm hết hàng hoặc bị giới hạn theo tồn kho.
    """
    session_quantities = session_store.quantities()
    if not session_quantities:
        session_store.clear()
        return []

    warnings = []
    with transaction.atomic():
        db_quantities = db_store.quantities()
        products = {
            p.pk: p
            for p in Product.objects.filter(pk__in=session_quantities, is_active=True)
        }
        for product_id, session_qty in session_quantities.items():
            product = products.get(product_id)
            if product is None:
                continue
            if product.stock == 0:
                warnings.append(f"Sản phẩm '{product.name}' đã hết hàng nên không được gộp vào giỏ.")
                continue
            existing_qty = db_quantities.get(product_id, 0)
            merged_qty = existing_qty + session_qty
            if merged_qty > product.stock:
                capped_qty = max(product.stock, existing_qty)
                if capped_qty != existing_qty:
                    db_store.set(product, capped_qty, refresh_price=True)
                warnings.append(
                    f"Số lượng '{product.name}' trong giỏ được điều chỉnh tối đa còn {product.stock} theo tồn kho."
                )
            else:
                db_store.set(product, merged_qty, refresh_price=True)
        session_store.clear()
    return warnings
