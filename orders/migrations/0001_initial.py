# Generated for CN11 (Order + OrderItem)

import accounts.validators
import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("catalog", "0002_product_productimage_product_product_price_gt_0"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Order",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("receiver", models.CharField(max_length=150, verbose_name="Người nhận")),
                (
                    "phone",
                    models.CharField(
                        max_length=15,
                        validators=[accounts.validators.validate_vn_phone],
                        verbose_name="Số điện thoại",
                    ),
                ),
                (
                    "street",
                    models.CharField(max_length=255, verbose_name="Số nhà, tên đường"),
                ),
                ("ward", models.CharField(max_length=100, verbose_name="Phường / Xã")),
                (
                    "district",
                    models.CharField(
                        blank=True, default="", max_length=100, verbose_name="Quận / Huyện"
                    ),
                ),
                (
                    "province",
                    models.CharField(max_length=100, verbose_name="Tỉnh / Thành phố"),
                ),
                ("note", models.TextField(blank=True, verbose_name="Ghi chú")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Chờ xác nhận"),
                            ("confirmed", "Đã xác nhận"),
                            ("shipping", "Đang giao"),
                            ("completed", "Hoàn tất"),
                            ("cancelled", "Đã hủy"),
                        ],
                        default="pending",
                        max_length=20,
                        verbose_name="Trạng thái",
                    ),
                ),
                (
                    "payment_method",
                    models.CharField(
                        choices=[("cod", "Thanh toán khi nhận hàng (COD)")],
                        default="cod",
                        max_length=20,
                        verbose_name="Phương thức thanh toán",
                    ),
                ),
                (
                    "subtotal",
                    models.DecimalField(
                        decimal_places=0,
                        max_digits=12,
                        validators=[django.core.validators.MinValueValidator(0)],
                        verbose_name="Tạm tính (VND)",
                    ),
                ),
                (
                    "shipping_fee",
                    models.DecimalField(
                        decimal_places=0,
                        default=0,
                        max_digits=12,
                        validators=[django.core.validators.MinValueValidator(0)],
                        verbose_name="Phí vận chuyển (VND)",
                    ),
                ),
                (
                    "total",
                    models.DecimalField(
                        decimal_places=0,
                        max_digits=12,
                        validators=[django.core.validators.MinValueValidator(0)],
                        verbose_name="Tổng cộng (VND)",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="Ngày đặt"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="Ngày cập nhật"),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="orders",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Người dùng",
                    ),
                ),
            ],
            options={
                "verbose_name": "Đơn hàng",
                "verbose_name_plural": "Đơn hàng",
                "ordering": ["-created_at", "-id"],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("subtotal__gte", 0)),
                        name="order_subtotal_gte_0",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("shipping_fee__gte", 0)),
                        name="order_shipping_fee_gte_0",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("total__gte", 0)),
                        name="order_total_gte_0",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="OrderItem",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "product_name",
                    models.CharField(
                        max_length=200, verbose_name="Tên sản phẩm lúc mua"
                    ),
                ),
                (
                    "unit_price",
                    models.DecimalField(
                        decimal_places=0,
                        max_digits=12,
                        validators=[django.core.validators.MinValueValidator(1)],
                        verbose_name="Đơn giá lúc mua (VND)",
                    ),
                ),
                (
                    "quantity",
                    models.PositiveIntegerField(
                        validators=[django.core.validators.MinValueValidator(1)],
                        verbose_name="Số lượng",
                    ),
                ),
                (
                    "order",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="orders.order",
                        verbose_name="Đơn hàng",
                    ),
                ),
                (
                    "product",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="order_items",
                        to="catalog.product",
                        verbose_name="Sản phẩm",
                    ),
                ),
            ],
            options={
                "verbose_name": "Chi tiết đơn hàng",
                "verbose_name_plural": "Chi tiết đơn hàng",
                "ordering": ["id"],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("unit_price__gt", 0)),
                        name="orderitem_unit_price_gt_0",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("quantity__gte", 1)),
                        name="orderitem_quantity_gte_1",
                    ),
                ],
            },
        ),
    ]
