from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from accounts.validators import validate_vn_phone
from catalog.models import Product


class Coupon(models.Model):
    """Mã giảm giá áp dụng cho đơn hàng (CN22)."""

    class DiscountType(models.TextChoices):
        PERCENT = "percent", "Phần trăm (%)"
        FIXED = "fixed", "Số tiền cố định (VND)"

    code = models.CharField("Mã giảm giá", max_length=50, unique=True)
    discount_type = models.CharField(
        "Loại giảm giá",
        max_length=15,
        choices=DiscountType.choices,
        default=DiscountType.PERCENT,
    )
    discount_value = models.DecimalField(
        "Giá trị giảm",
        max_digits=12,
        decimal_places=0,
        validators=[MinValueValidator(1)],
    )
    max_discount_amount = models.DecimalField(
        "Giảm tối đa (VND)",
        max_digits=12,
        decimal_places=0,
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
    )
    min_order_amount = models.DecimalField(
        "Đơn tối thiểu (VND)",
        max_digits=12,
        decimal_places=0,
        default=0,
        validators=[MinValueValidator(0)],
    )
    usage_limit = models.PositiveIntegerField(
        "Giới hạn lượt dùng",
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
    )
    used_count = models.PositiveIntegerField("Số lượt đã dùng", default=0)
    valid_from = models.DateTimeField("Hiệu lực từ", null=True, blank=True)
    valid_until = models.DateTimeField("Hết hạn lúc", null=True, blank=True)
    is_active = models.BooleanField("Đang kích hoạt", default=True)
    created_at = models.DateTimeField("Ngày tạo", auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "Mã giảm giá"
        verbose_name_plural = "Mã giảm giá"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(discount_value__gt=0),
                name="coupon_discount_value_gt_0",
            ),
            models.CheckConstraint(
                condition=models.Q(min_order_amount__gte=0),
                name="coupon_min_order_amount_gte_0",
            ),
        ]

    def clean(self):
        super().clean()
        self.code = (self.code or "").strip().upper()
        if (
            self.discount_type == self.DiscountType.PERCENT
            and self.discount_value is not None
            and self.discount_value > 100
        ):
            raise ValidationError(
                {"discount_value": "Giảm giá theo phần trăm không được vượt quá 100%."}
            )
        if self.valid_from and self.valid_until and self.valid_until < self.valid_from:
            raise ValidationError(
                {"valid_until": "Thời điểm hết hạn phải sau thời điểm bắt đầu hiệu lực."}
            )

    def save(self, *args, **kwargs):
        self.code = (self.code or "").strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.code


class Order(models.Model):
    """Đơn hàng (CN11): lưu snapshot địa chỉ và tổng tiền tại thời điểm đặt."""

    class Status(models.TextChoices):
        PENDING = "pending", "Chờ xác nhận"
        CONFIRMED = "confirmed", "Đã xác nhận"
        SHIPPING = "shipping", "Đang giao"
        COMPLETED = "completed", "Hoàn tất"
        CANCELLED = "cancelled", "Đã hủy"

    class PaymentMethod(models.TextChoices):
        COD = "cod", "Thanh toán khi nhận hàng (COD)"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Người dùng",
        on_delete=models.PROTECT,
        related_name="orders",
    )
    receiver = models.CharField("Người nhận", max_length=150)
    phone = models.CharField(
        "Số điện thoại", max_length=15, validators=[validate_vn_phone]
    )
    street = models.CharField("Số nhà, tên đường", max_length=255)
    ward = models.CharField("Phường / Xã", max_length=100)
    district = models.CharField("Quận / Huyện", max_length=100, blank=True, default="")
    province = models.CharField("Tỉnh / Thành phố", max_length=100)
    note = models.TextField("Ghi chú", blank=True)

    status = models.CharField(
        "Trạng thái",
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    payment_method = models.CharField(
        "Phương thức thanh toán",
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.COD,
    )
    coupon = models.ForeignKey(
        Coupon,
        verbose_name="Mã giảm giá",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )
    coupon_code = models.CharField(
        "Mã giảm giá lúc đặt", max_length=50, blank=True, default=""
    )
    discount_amount = models.DecimalField(
        "Giảm giá (VND)",
        max_digits=12,
        decimal_places=0,
        default=0,
        validators=[MinValueValidator(0)],
    )
    subtotal = models.DecimalField(
        "Tạm tính (VND)",
        max_digits=12,
        decimal_places=0,
        validators=[MinValueValidator(0)],
    )
    shipping_fee = models.DecimalField(
        "Phí vận chuyển (VND)",
        max_digits=12,
        decimal_places=0,
        default=0,
        validators=[MinValueValidator(0)],
    )
    total = models.DecimalField(
        "Tổng cộng (VND)",
        max_digits=12,
        decimal_places=0,
        validators=[MinValueValidator(0)],
    )
    created_at = models.DateTimeField("Ngày đặt", auto_now_add=True)
    updated_at = models.DateTimeField("Ngày cập nhật", auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "Đơn hàng"
        verbose_name_plural = "Đơn hàng"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(subtotal__gte=0), name="order_subtotal_gte_0"
            ),
            models.CheckConstraint(
                condition=models.Q(discount_amount__gte=0),
                name="order_discount_amount_gte_0",
            ),
            models.CheckConstraint(
                condition=models.Q(shipping_fee__gte=0), name="order_shipping_fee_gte_0"
            ),
            models.CheckConstraint(
                condition=models.Q(total__gte=0), name="order_total_gte_0"
            ),
        ]

    def __str__(self):
        return f"Đơn #{self.pk}"


class OrderItem(models.Model):
    """Dòng sản phẩm trong đơn hàng: lưu snapshot tên và đơn giá tại thời điểm mua."""

    order = models.ForeignKey(
        Order,
        verbose_name="Đơn hàng",
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(
        Product,
        verbose_name="Sản phẩm",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items",
    )
    product_name = models.CharField("Tên sản phẩm lúc mua", max_length=200)
    unit_price = models.DecimalField(
        "Đơn giá lúc mua (VND)",
        max_digits=12,
        decimal_places=0,
        validators=[MinValueValidator(1)],
    )
    quantity = models.PositiveIntegerField(
        "Số lượng", validators=[MinValueValidator(1)]
    )

    class Meta:
        ordering = ["id"]
        verbose_name = "Chi tiết đơn hàng"
        verbose_name_plural = "Chi tiết đơn hàng"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(unit_price__gt=0), name="orderitem_unit_price_gt_0"
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1), name="orderitem_quantity_gte_1"
            ),
        ]

    @property
    def line_total(self):
        return self.unit_price * self.quantity

    def __str__(self):
        return f"{self.product_name} x {self.quantity}"


class OrderStatusLog(models.Model):
    """Lịch sử đổi trạng thái đơn hàng (CN16)."""

    order = models.ForeignKey(
        Order,
        verbose_name="Đơn hàng",
        on_delete=models.CASCADE,
        related_name="status_logs",
    )
    from_status = models.CharField(
        "Trạng thái cũ", max_length=20, choices=Order.Status.choices, blank=True
    )
    to_status = models.CharField(
        "Trạng thái mới", max_length=20, choices=Order.Status.choices
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Người thực hiện",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_status_changes",
    )
    note = models.CharField("Ghi chú", max_length=255, blank=True)
    created_at = models.DateTimeField("Thời điểm đổi", auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        verbose_name = "Lịch sử trạng thái đơn hàng"
        verbose_name_plural = "Lịch sử trạng thái đơn hàng"

    def __str__(self):
        return f"Đơn #{self.order_id}: {self.from_status} -> {self.to_status}"
