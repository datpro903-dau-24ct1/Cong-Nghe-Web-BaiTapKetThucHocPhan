"""CN11: Kiểm thử Model Order + OrderItem (lưu snapshot giá/tên/địa chỉ, giữ đơn khi xóa sản phẩm)."""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase

from accounts.models import Address
from catalog import services as catalog_services
from orders.models import Order, OrderItem


class OrderModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = catalog_services.create_category("Scale Figure")
        cls.series = catalog_services.create_series("One Piece")
        cls.brand = catalog_services.create_brand("Good Smile Company")
        User = get_user_model()
        cls.user = User.objects.create_user(
            "buyer@example.com", "Matkhau!2345", full_name="Người Mua"
        )

    def make_product(self, name="Luffy Gear 5", price=1500000, stock=5):
        return catalog_services.create_product(
            name=name,
            category=self.category,
            series=self.series,
            brand=self.brand,
            price=price,
            stock=stock,
        )

    def make_order(self, **overrides):
        data = {
            "user": self.user,
            "receiver": "Nguyễn Văn A",
            "phone": "0901234567",
            "street": "123 Lê Lợi",
            "ward": "Phường Bến Nghé",
            "district": "Quận 1",
            "province": "TP. Hồ Chí Minh",
            "subtotal": 3000000,
            "shipping_fee": 30000,
            "total": 3030000,
        }
        data.update(overrides)
        return Order.objects.create(**data)

    def test_tao_don_hang_mac_dinh_trang_thai_pending_va_cod(self):
        order = self.make_order()
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertEqual(order.payment_method, Order.PaymentMethod.COD)
        self.assertEqual(str(order), f"Đơn #{order.pk}")

    def test_gia_va_ten_san_pham_doi_sau_khi_dat_khong_lam_doi_don_cu(self):
        product = self.make_product(name="Luffy Gear 5", price=1500000)
        order = self.make_order(subtotal=3000000, shipping_fee=0, total=3000000)
        item = OrderItem.objects.create(
            order=order,
            product=product,
            product_name=product.name,
            unit_price=product.price,
            quantity=2,
        )

        # Đổi tên và giá sản phẩm sau khi đặt hàng
        product.name = "Luffy Gear 5 (Bản mới)"
        product.price = 2200000
        product.save()

        item.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(item.product_name, "Luffy Gear 5")
        self.assertEqual(item.unit_price, 1500000)
        self.assertEqual(item.line_total, 3000000)
        self.assertEqual(order.total, 3000000)

    def test_xoa_san_pham_khong_lam_mat_don_hang_cu(self):
        product = self.make_product(name="Zoro Wano", price=1800000)
        order = self.make_order(subtotal=1800000, shipping_fee=0, total=1800000)
        item = OrderItem.objects.create(
            order=order,
            product=product,
            product_name=product.name,
            unit_price=product.price,
            quantity=1,
        )

        product.delete()

        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(OrderItem.objects.count(), 1)
        item.refresh_from_db()
        self.assertIsNone(item.product)
        self.assertEqual(item.product_name, "Zoro Wano")
        self.assertEqual(item.unit_price, 1800000)
        self.assertEqual(item.line_total, 1800000)

    def test_sua_hoac_xoa_so_dia_chi_khong_anh_huong_dia_chi_don_hang(self):
        addr = Address.objects.create(
            user=self.user,
            receiver="Nguyễn Văn A",
            phone="0901234567",
            street="123 Lê Lợi",
            ward="Phường Bến Nghé",
            district="Quận 1",
            province="TP. Hồ Chí Minh",
            is_default=True,
        )
        order = self.make_order(
            receiver=addr.receiver,
            phone=addr.phone,
            street=addr.street,
            ward=addr.ward,
            district=addr.district,
            province=addr.province,
        )
        addr.street = "999 Nguyễn Huệ"
        addr.save()
        addr.delete()

        order.refresh_from_db()
        self.assertEqual(order.street, "123 Lê Lợi")
        self.assertEqual(order.receiver, "Nguyễn Văn A")

    def test_xoa_don_hang_thi_xoa_cac_dong_order_item(self):
        product = self.make_product()
        order = self.make_order()
        OrderItem.objects.create(
            order=order,
            product=product,
            product_name=product.name,
            unit_price=product.price,
            quantity=1,
        )
        order.delete()
        self.assertEqual(OrderItem.objects.count(), 0)

    def test_khong_cho_xoa_user_dang_co_don_hang(self):
        self.make_order()
        with self.assertRaises(ProtectedError):
            self.user.delete()

    def test_rang_buoc_so_luong_va_don_gia_hop_le(self):
        product = self.make_product()
        order = self.make_order()

        with self.assertRaises(IntegrityError), transaction.atomic():
            OrderItem.objects.create(
                order=order,
                product=product,
                product_name=product.name,
                unit_price=product.price,
                quantity=0,
            )

        with self.assertRaises(IntegrityError), transaction.atomic():
            OrderItem.objects.create(
                order=order,
                product=product,
                product_name=product.name,
                unit_price=0,
                quantity=1,
            )

    def test_sdt_nguoi_nhan_sai_dinh_dang_bi_chan_khi_full_clean(self):
        order = Order(
            user=self.user,
            receiver="Nguyễn Văn A",
            phone="12345",
            street="123 Lê Lợi",
            ward="Phường Bến Nghé",
            district="Quận 1",
            province="TP. Hồ Chí Minh",
            subtotal=1500000,
            shipping_fee=0,
            total=1500000,
        )
        with self.assertRaises(ValidationError):
            order.full_clean()
