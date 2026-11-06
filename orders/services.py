"""Nghiệp vụ đặt hàng, vận chuyển COD & mã giảm giá (CN12, CN13, CN14, CN16, CN22).
Lỗi nghiệp vụ -> ValidationError.
"""
import re
import unicodedata
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from accounts.models import Address
from accounts.validators import normalize_phone, validate_vn_phone
from carts.models import CartItem
from catalog.models import Product

from .models import Coupon, Order, OrderItem, OrderStatusLog

ALLOWED_STATUS_TRANSITIONS = {
    Order.Status.PENDING: {Order.Status.CONFIRMED, Order.Status.CANCELLED},
    Order.Status.CONFIRMED: {Order.Status.SHIPPING, Order.Status.CANCELLED},
    Order.Status.SHIPPING: {Order.Status.COMPLETED},
    Order.Status.COMPLETED: set(),
    Order.Status.CANCELLED: set(),
}

VND_QUANTIZE = Decimal("1")
INNER_SHIPPING_FEE = Decimal(30000)
OUTER_SHIPPING_FEE = Decimal(40000)

INNER_PROVINCES = {
    "ho chi minh",
    "hcm",
    "tphcm",
    "sai gon",
    "ha noi",
    "hn",
}

OUTER_PROVINCES = {
    "an giang",
    "ba ria vung tau",
    "vung tau",
    "bac giang",
    "bac kan",
    "bac lieu",
    "bac ninh",
    "ben tre",
    "binh dinh",
    "binh duong",
    "binh phuoc",
    "binh thuan",
    "ca mau",
    "can tho",
    "cao bang",
    "da nang",
    "dak lak",
    "dac lac",
    "dak nong",
    "dac nong",
    "dien bien",
    "dong nai",
    "dong thap",
    "gia lai",
    "ha giang",
    "ha nam",
    "ha tinh",
    "hai duong",
    "hai phong",
    "hau giang",
    "hoa binh",
    "hung yen",
    "khanh hoa",
    "kien giang",
    "kon tum",
    "lai chau",
    "lam dong",
    "lang son",
    "lao cai",
    "long an",
    "nam dinh",
    "nghe an",
    "ninh binh",
    "ninh thuan",
    "phu tho",
    "phu yen",
    "quang binh",
    "quang nam",
    "quang ngai",
    "quang ninh",
    "quang tri",
    "soc trang",
    "son la",
    "tay ninh",
    "thai binh",
    "thai nguyen",
    "thanh hoa",
    "thua thien hue",
    "hue",
    "tien giang",
    "tra vinh",
    "tuyen quang",
    "vinh long",
    "vinh phuc",
    "yen bai",
}


def quantize_vnd(value):
    """Làm tròn số tiền về hàng đơn vị VND (ROUND_HALF_UP), không dùng float."""
    try:
        dec = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError("Số tiền không hợp lệ.", code="invalid_amount")
    return dec.quantize(VND_QUANTIZE, rounding=ROUND_HALF_UP)


def _parse_single_coupon_code(raw_code) -> str:
    """Chuẩn hóa 1 mã giảm giá; chặn trường hợp truyền nhiều mã cùng lúc (CN22)."""
    if raw_code is None:
        return ""
    if isinstance(raw_code, (list, tuple, set)):
        items = [str(c).strip() for c in raw_code if str(c).strip()]
        if len(items) > 1:
            raise ValidationError(
                "Mỗi đơn hàng chỉ được áp dụng tối đa một mã giảm giá.",
                code="multiple_coupons_not_allowed",
            )
        raw_code = items[0] if items else ""
    if not isinstance(raw_code, str):
        raise ValidationError("Mã giảm giá không hợp lệ.", code="invalid_coupon")
    cleaned = raw_code.strip()
    if not cleaned:
        return ""
    parts = [p for p in re.split(r"[,;\s]+", cleaned) if p]
    if len(parts) > 1:
        raise ValidationError(
            "Mỗi đơn hàng chỉ được áp dụng tối đa một mã giảm giá.",
            code="multiple_coupons_not_allowed",
        )
    return parts[0].upper()


def _validate_coupon_object(coupon, subtotal, *, now=None):
    """Kiểm tra điều kiện của Coupon và trả về số tiền được giảm (VND)."""
    now = now or timezone.now()
    subtotal = quantize_vnd(subtotal)

    if coupon is None or not coupon.is_active:
        raise ValidationError(
            "Mã giảm giá không hợp lệ hoặc không tồn tại.", code="invalid_coupon"
        )
    if (coupon.valid_from and now < coupon.valid_from) or (
        coupon.valid_until and now > coupon.valid_until
    ):
        raise ValidationError(
            "Mã giảm giá đã hết hạn hoặc chưa đến thời gian áp dụng.",
            code="coupon_expired",
        )
    if coupon.usage_limit is not None and coupon.used_count >= coupon.usage_limit:
        raise ValidationError(
            "Mã giảm giá đã hết lượt sử dụng.", code="coupon_usage_exceeded"
        )
    if subtotal < coupon.min_order_amount:
        raise ValidationError(
            f"Đơn hàng cần tối thiểu {coupon.min_order_amount:,.0f} ₫ để áp dụng mã '{coupon.code}'.",
            code="coupon_min_amount_not_met",
        )

    if coupon.discount_type == Coupon.DiscountType.PERCENT:
        discount = quantize_vnd(subtotal * coupon.discount_value / Decimal(100))
    else:
        discount = quantize_vnd(coupon.discount_value)

    if coupon.max_discount_amount is not None:
        discount = min(discount, quantize_vnd(coupon.max_discount_amount))
    return min(discount, subtotal)


def validate_and_calculate_coupon(raw_code, subtotal):
    """Kiểm tra mã giảm giá và tính số tiền giảm (trả về (coupon, discount_amount))."""
    code = _parse_single_coupon_code(raw_code)
    if not code:
        return None, Decimal(0)
    coupon = Coupon.objects.filter(code=code).first()
    discount = _validate_coupon_object(coupon, subtotal)
    return coupon, discount


def _normalize_province_key(province):
    """Bỏ dấu tiếng Việt, ký tự đặc biệt và tiền tố 'tỉnh'/'thành phố'/'tp' để đối chiếu vùng."""
    text = (province or "").strip().lower().replace("đ", "d")
    text = "".join(
        ch
        for ch in unicodedata.normalize("NFD", text)
        if unicodedata.category(ch) != "Mn"
    )
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    for prefix in ("thanh pho ", "tinh ", "tp "):
        if text.startswith(prefix):
            text = text[len(prefix) :].strip()
    return text


def calculate_shipping_fee(province):
    """Tính phí vận chuyển theo tỉnh/thành (CN13). Ngoài vùng giao -> ValidationError."""
    key = _normalize_province_key(province)
    if key in INNER_PROVINCES:
        return INNER_SHIPPING_FEE
    if key in OUTER_PROVINCES:
        return OUTER_SHIPPING_FEE
    raise ValidationError(
        "Địa chỉ nằm ngoài vùng giao hàng hỗ trợ (chỉ giao trong lãnh thổ Việt Nam).",
        code="out_of_delivery_area",
    )


def _resolve_shipping_address(
    user, *, address_id, receiver, phone, street, ward, district, province
):
    """Lấy thông tin người nhận từ sổ địa chỉ của user hoặc từ dữ liệu nhập trực tiếp."""
    if address_id not in (None, ""):
        try:
            addr_pk = int(address_id)
        except (TypeError, ValueError):
            raise ValidationError("Địa chỉ giao hàng không hợp lệ.", code="invalid_address")
        address = Address.objects.filter(user=user, pk=addr_pk).first()
        if address is None:
            raise ValidationError("Địa chỉ giao hàng không hợp lệ.", code="invalid_address")
        return {
            "receiver": address.receiver,
            "phone": address.phone,
            "street": address.street,
            "ward": address.ward,
            "district": "",
            "province": address.province,
        }

    cleaned = {
        "receiver": (receiver or "").strip(),
        "phone": normalize_phone(phone),
        "street": (street or "").strip(),
        "ward": (ward or "").strip(),
        "district": (district or "").strip(),
        "province": (province or "").strip(),
    }
    errors = {}
    for field, label in (
        ("receiver", "Người nhận"),
        ("street", "Số nhà, tên đường"),
        ("ward", "Phường / Xã"),
        ("province", "Tỉnh / Thành phố"),
    ):
        if not cleaned[field]:
            errors[field] = ValidationError(
                f"{label} không được để trống.", code=f"blank_{field}"
            )
    try:
        validate_vn_phone(cleaned["phone"])
    except ValidationError as exc:
        errors["phone"] = exc

    if errors:
        raise ValidationError(errors)
    return cleaned


def place_order(
    user,
    *,
    address_id=None,
    receiver="",
    phone="",
    street="",
    ward="",
    district="",
    province="",
    note="",
    payment_method=Order.PaymentMethod.COD,
    shipping_fee=None,
    coupon_code="",
):
    """Tạo đơn hàng COD từ giỏ DB của user, áp mã giảm giá (nếu có), tính phí ship và trừ tồn kho (CN12, CN13, CN22)."""
    if payment_method != Order.PaymentMethod.COD:
        raise ValidationError(
            "Phương thức thanh toán không hợp lệ.", code="invalid_payment_method"
        )

    parsed_coupon_code = _parse_single_coupon_code(coupon_code)

    shipping = _resolve_shipping_address(
        user,
        address_id=address_id,
        receiver=receiver,
        phone=phone,
        street=street,
        ward=ward,
        district=district,
        province=province,
    )
    area_fee = calculate_shipping_fee(shipping["province"])
    if shipping_fee is None:
        final_shipping_fee = area_fee
    else:
        final_shipping_fee = quantize_vnd(shipping_fee)
        if final_shipping_fee < 0:
            raise ValidationError(
                "Phí vận chuyển không hợp lệ.", code="invalid_shipping_fee"
            )

    note = (note or "").strip()
    User = get_user_model()

    with transaction.atomic():
        # Khóa dòng User để tuần tự hóa 2 request bấm đặt hàng cùng lúc của cùng một người.
        User.objects.select_for_update().get(pk=user.pk)

        cart_items = list(
            CartItem.objects.filter(cart__user=user).order_by("id")
        )
        if not cart_items:
            raise ValidationError("Giỏ hàng của bạn đang trống.", code="empty_cart")

        product_ids = [item.product_id for item in cart_items]
        # Khóa các dòng Product theo thứ tự pk tăng dần để tránh deadlock khi mua đồng thời.
        locked_products = {
            p.pk: p
            for p in Product.objects.select_for_update()
            .filter(pk__in=product_ids)
            .order_by("pk")
        }

        subtotal = Decimal(0)
        order_lines = []
        for cart_item in cart_items:
            product = locked_products.get(cart_item.product_id)
            if product is None or not product.is_active:
                raise ValidationError(
                    "Một số sản phẩm trong giỏ không còn được bán.",
                    code="product_unavailable",
                )
            if product.stock == 0:
                raise ValidationError(
                    f"Sản phẩm '{product.name}' đã hết hàng.",
                    code="out_of_stock",
                )
            if cart_item.quantity > product.stock:
                raise ValidationError(
                    f"Sản phẩm '{product.name}' chỉ còn {product.stock} trong kho.",
                    code="exceeds_stock",
                )
            unit_price = quantize_vnd(product.price)
            line_total = quantize_vnd(unit_price * cart_item.quantity)
            subtotal += line_total
            order_lines.append((product, cart_item.quantity, unit_price))

        subtotal = quantize_vnd(subtotal)

        coupon = None
        discount_amount = Decimal(0)
        if parsed_coupon_code:
            coupon = (
                Coupon.objects.select_for_update()
                .filter(code=parsed_coupon_code)
                .first()
            )
            discount_amount = _validate_coupon_object(coupon, subtotal)
            coupon.used_count += 1
            coupon.save(update_fields=["used_count"])

        total = quantize_vnd(subtotal - discount_amount + final_shipping_fee)

        order = Order(
            user=user,
            note=note,
            payment_method=payment_method,
            coupon=coupon,
            coupon_code=coupon.code if coupon else "",
            discount_amount=discount_amount,
            subtotal=subtotal,
            shipping_fee=final_shipping_fee,
            total=total,
            **shipping,
        )
        order.full_clean()
        order.save()

        for product, quantity, unit_price in order_lines:
            OrderItem.objects.create(
                order=order,
                product=product,
                product_name=product.name,
                unit_price=unit_price,
                quantity=quantity,
            )
            product.stock -= quantity
            product.save(update_fields=["stock", "updated_at"])

        CartItem.objects.filter(cart__user=user).delete()
        return order


def _restore_order_stock(order):
    """Hoàn lại tồn kho và lượt dùng mã giảm giá khi đơn hàng bị hủy (chạy trong atomic)."""
    items = list(order.items.all())
    product_ids = [item.product_id for item in items if item.product_id is not None]
    if product_ids:
        locked_products = {
            p.pk: p
            for p in Product.objects.select_for_update()
            .filter(pk__in=product_ids)
            .order_by("pk")
        }
        for item in items:
            product = locked_products.get(item.product_id)
            if product is not None:
                product.stock += item.quantity
                product.save(update_fields=["stock", "updated_at"])

    if order.coupon_id:
        locked_coupon = (
            Coupon.objects.select_for_update().filter(pk=order.coupon_id).first()
        )
        if locked_coupon is not None and locked_coupon.used_count > 0:
            locked_coupon.used_count -= 1
            locked_coupon.save(update_fields=["used_count"])


def can_transition_order_status(from_status, to_status):
    """Kiểm tra có được phép chuyển trạng thái từ from_status sang to_status không."""
    return to_status in ALLOWED_STATUS_TRANSITIONS.get(from_status, set())


def transition_order_status(order_id, new_status, *, actor=None, note=""):
    """Đổi trạng thái đơn hàng theo đúng thứ tự, hoàn kho nếu hủy, và ghi lịch sử (CN16)."""
    if new_status not in Order.Status.values:
        raise ValidationError(
            "Trạng thái đơn hàng không hợp lệ.", code="invalid_status"
        )
    note = (note or "").strip()

    with transaction.atomic():
        order = Order.objects.select_for_update().filter(pk=order_id).first()
        if order is None:
            raise ValidationError(
                "Không tìm thấy đơn hàng.", code="order_not_found"
            )
        old_status = order.status
        if not can_transition_order_status(old_status, new_status):
            old_label = Order.Status(old_status).label
            new_label = Order.Status(new_status).label
            raise ValidationError(
                f"Không thể chuyển trạng thái đơn hàng từ '{old_label}' sang '{new_label}'.",
                code="invalid_status_transition",
            )

        if new_status == Order.Status.CANCELLED:
            _restore_order_stock(order)

        order.status = new_status
        order.save(update_fields=["status", "updated_at"])
        OrderStatusLog.objects.create(
            order=order,
            from_status=old_status,
            to_status=new_status,
            changed_by=actor,
            note=note,
        )
        return order


def cancel_order(user, order_id):
    """Khách hàng hủy đơn của mình (chỉ khi đang chờ xác nhận) và hoàn lại tồn kho (CN14, CN16)."""
    with transaction.atomic():
        order = (
            Order.objects.select_for_update()
            .filter(user=user, pk=order_id)
            .first()
        )
        if order is None:
            raise ValidationError(
                "Không tìm thấy đơn hàng.", code="order_not_found"
            )
        if order.status == Order.Status.CANCELLED:
            raise ValidationError(
                "Đơn hàng này đã được hủy trước đó.", code="already_cancelled"
            )
        if order.status != Order.Status.PENDING:
            raise ValidationError(
                "Không thể hủy đơn hàng ở trạng thái hiện tại.",
                code="cannot_cancel",
            )

        old_status = order.status
        _restore_order_stock(order)

        order.status = Order.Status.CANCELLED
        order.save(update_fields=["status", "updated_at"])
        OrderStatusLog.objects.create(
            order=order,
            from_status=old_status,
            to_status=Order.Status.CANCELLED,
            changed_by=user,
            note="Khách hàng tự hủy đơn",
        )
        return order
