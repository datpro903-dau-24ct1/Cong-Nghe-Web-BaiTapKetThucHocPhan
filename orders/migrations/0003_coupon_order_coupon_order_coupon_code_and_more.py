# Generated for CN22 (Coupon & Order coupon fields)

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0002_orderstatuslog"),
    ]

    operations = [
        migrations.CreateModel(
            name="Coupon",
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
                    "code",
                    models.CharField(
                        max_length=50, unique=True, verbose_name="Mã giảm giá"
                    ),
                ),
                (
                    "discount_type",
                    models.CharField(
                        choices=[
                            ("percent", "Phần trăm (%)"),
                            ("fixed", "Số tiền cố định (VND)"),
                        ],
                        default="percent",
                        max_length=15,
                        verbose_name="Loại giảm giá",
                    ),
                ),
                (
                    "discount_value",
                    models.DecimalField(
                        decimal_places=0,
                        max_digits=12,
                        validators=[django.core.validators.MinValueValidator(1)],
                        verbose_name="Giá trị giảm",
                    ),
                ),
                (
                    "max_discount_amount",
                    models.DecimalField(
                        blank=True,
                        decimal_places=0,
                        max_digits=12,
                        null=True,
                        validators=[django.core.validators.MinValueValidator(1)],
                        verbose_name="Giảm tối đa (VND)",
                    ),
                ),
                (
                    "min_order_amount",
                    models.DecimalField(
                        decimal_places=0,
                        default=0,
                        max_digits=12,
                        validators=[django.core.validators.MinValueValidator(0)],
                        verbose_name="Đơn tối thiểu (VND)",
                    ),
                ),
                (
                    "usage_limit",
                    models.PositiveIntegerField(
                        blank=True,
                        null=True,
                        validators=[django.core.validators.MinValueValidator(1)],
                        verbose_name="Giới hạn lượt dùng",
                    ),
                ),
                (
                    "used_count",
                    models.PositiveIntegerField(
                        default=0, verbose_name="Số lượt đã dùng"
                    ),
                ),
                (
                    "valid_from",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="Hiệu lực từ"
                    ),
                ),
                (
                    "valid_until",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="Hết hạn lúc"
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(default=True, verbose_name="Đang kích hoạt"),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="Ngày tạo"),
                ),
            ],
            options={
                "verbose_name": "Mã giảm giá",
                "verbose_name_plural": "Mã giảm giá",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddField(
            model_name="order",
            name="coupon",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="orders",
                to="orders.coupon",
                verbose_name="Mã giảm giá",
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="coupon_code",
            field=models.CharField(
                blank=True,
                default="",
                max_length=50,
                verbose_name="Mã giảm giá lúc đặt",
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="discount_amount",
            field=models.DecimalField(
                decimal_places=0,
                default=0,
                max_digits=12,
                validators=[django.core.validators.MinValueValidator(0)],
                verbose_name="Giảm giá (VND)",
            ),
        ),
        migrations.AddConstraint(
            model_name="coupon",
            constraint=models.CheckConstraint(
                condition=models.Q(("discount_value__gt", 0)),
                name="coupon_discount_value_gt_0",
            ),
        ),
        migrations.AddConstraint(
            model_name="coupon",
            constraint=models.CheckConstraint(
                condition=models.Q(("min_order_amount__gte", 0)),
                name="coupon_min_order_amount_gte_0",
            ),
        ),
        migrations.AddConstraint(
            model_name="order",
            constraint=models.CheckConstraint(
                condition=models.Q(("discount_amount__gte", 0)),
                name="order_discount_amount_gte_0",
            ),
        ),
    ]
