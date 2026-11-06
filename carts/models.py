from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from catalog.models import Product


class Cart(models.Model):
    """Giỏ hàng của người dùng đã đăng nhập (khách chưa đăng nhập dùng session)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, verbose_name="Người dùng",
        on_delete=models.CASCADE, related_name="cart",
    )
    created_at = models.DateTimeField("Ngày tạo", auto_now_add=True)
    updated_at = models.DateTimeField("Ngày cập nhật", auto_now=True)

    class Meta:
        verbose_name = "Giỏ hàng"
        verbose_name_plural = "Giỏ hàng"

    def __str__(self):
        return f"Giỏ của {self.user}"


class CartItem(models.Model):
    cart = models.ForeignKey(
        Cart, verbose_name="Giỏ hàng", on_delete=models.CASCADE, related_name="items"
    )
    product = models.ForeignKey(
        Product, verbose_name="Sản phẩm", on_delete=models.CASCADE, related_name="cart_items"
    )
    quantity = models.PositiveIntegerField("Số lượng", validators=[MinValueValidator(1)])
    # Giá lúc thêm vào giỏ, chỉ để cảnh báo khi giá đổi; giá tính tiền luôn lấy từ Product.
    unit_price = models.DecimalField("Giá lúc thêm (VND)", max_digits=12, decimal_places=0)
    created_at = models.DateTimeField("Ngày thêm", auto_now_add=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "Dòng giỏ hàng"
        verbose_name_plural = "Dòng giỏ hàng"
        constraints = [
            models.UniqueConstraint(fields=["cart", "product"], name="cartitem_unique_product_per_cart"),
            models.CheckConstraint(condition=models.Q(quantity__gte=1), name="cartitem_quantity_gte_1"),
        ]

    def __str__(self):
        return f"{self.product} x {self.quantity}"
