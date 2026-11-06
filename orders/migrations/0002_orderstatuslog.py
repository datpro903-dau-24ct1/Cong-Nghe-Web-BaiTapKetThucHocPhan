# Generated for CN16 (OrderStatusLog)

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="OrderStatusLog",
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
                    "from_status",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("pending", "Chờ xác nhận"),
                            ("confirmed", "Đã xác nhận"),
                            ("shipping", "Đang giao"),
                            ("completed", "Hoàn tất"),
                            ("cancelled", "Đã hủy"),
                        ],
                        max_length=20,
                        verbose_name="Trạng thái cũ",
                    ),
                ),
                (
                    "to_status",
                    models.CharField(
                        choices=[
                            ("pending", "Chờ xác nhận"),
                            ("confirmed", "Đã xác nhận"),
                            ("shipping", "Đang giao"),
                            ("completed", "Hoàn tất"),
                            ("cancelled", "Đã hủy"),
                        ],
                        max_length=20,
                        verbose_name="Trạng thái mới",
                    ),
                ),
                (
                    "note",
                    models.CharField(blank=True, max_length=255, verbose_name="Ghi chú"),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Thời điểm đổi"
                    ),
                ),
                (
                    "changed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="order_status_changes",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Người thực hiện",
                    ),
                ),
                (
                    "order",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="status_logs",
                        to="orders.order",
                        verbose_name="Đơn hàng",
                    ),
                ),
            ],
            options={
                "verbose_name": "Lịch sử trạng thái đơn hàng",
                "verbose_name_plural": "Lịch sử trạng thái đơn hàng",
                "ordering": ["created_at", "id"],
            },
        ),
    ]
