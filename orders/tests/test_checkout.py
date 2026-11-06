"""CN12: Kiểm thử đặt hàng (checkout) + trừ tồn kho + các trường hợp biên."""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts import services as account_services
from carts import services as cart_services
from carts.models import CartItem
from carts.stores import DbCartStore
from catalog import services as catalog_services
from orders import selectors, services
from orders.models import Order, OrderItem

PASSWORD = "Matkhau!2345"


class CheckoutBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = catalog_services.create_category("Scale Figure")
        cls.series = catalog_services.create_series("One Piece")
        cls.brand = catalog_services.create_brand("Good Smile Company")
        User = get_user_model()
        cls.user = User.objects.create_user(
            "buyer@example.com", PASSWORD, full_name="Người Mua"
        )
        cls.other_user = User.objects.create_user(
            "other@example.com", PASSWORD, full_name="Người Khác"
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

    def make_address(self, user=None, **overrides):
        data = {
            "receiver": "Nguyễn Văn A",
            "phone": "0901234567",
            "street": "123 Lê Lợi",
            "ward": "Phường Bến Nghé",
            "district": "Quận 1",
            "province": "TP. Hồ Chí Minh",
            "is_default": True,
        }
        data.update(overrides)
        return account_services.create_address(user or self.user, **data)

    def add_to_user_cart(self, product, quantity=1, user=None):
        cart_services.add_item(DbCartStore(user or self.user), product.pk, quantity)


class PlaceOrderServiceTests(CheckoutBase):
    def setUp(self):
        self.p1 = self.make_product("Luffy", price=1500000, stock=5)
        self.p2 = self.make_product("Zoro", price=1000000, stock=3)
        self.addr = self.make_address()

    def test_dat_hang_thanh_cong_tru_ton_kho_va_xoa_gio_hang(self):
        self.add_to_user_cart(self.p1, 2)
        self.add_to_user_cart(self.p2, 1)

        order = services.place_order(
            self.user, address_id=self.addr.pk, note="Giao giờ hành chính"
        )

        self.assertEqual(order.user, self.user)
        self.assertEqual(order.receiver, "Nguyễn Văn A")
        self.assertEqual(order.phone, "0901234567")
        self.assertEqual(order.subtotal, 4000000)
        self.assertEqual(order.shipping_fee, 30000)
        self.assertEqual(order.total, 4030000)
        self.assertEqual(order.note, "Giao giờ hành chính")
        self.assertEqual(order.status, Order.Status.PENDING)

        items = list(order.items.all())
        self.assertEqual(len(items), 2)
        self.assertEqual(
            [(i.product_name, i.unit_price, i.quantity) for i in items],
            [("Luffy", 1500000, 2), ("Zoro", 1000000, 1)],
        )

        self.p1.refresh_from_db()
        self.p2.refresh_from_db()
        self.assertEqual(self.p1.stock, 3)
        self.assertEqual(self.p2.stock, 2)
        self.assertEqual(DbCartStore(self.user).quantities(), {})

    def test_dat_hang_bang_dia_chi_nhap_tay(self):
        self.add_to_user_cart(self.p1, 1)
        order = services.place_order(
            self.user,
            receiver="Trần Thị B",
            phone="+84 912 345 678",
            street="45 Nguyễn Huệ",
            ward="Phường Bến Nghé",
            province="TP. Hồ Chí Minh",
        )
        self.assertEqual(order.receiver, "Trần Thị B")
        self.assertEqual(order.phone, "0912345678")
        self.assertEqual(order.total, 1530000)

    def test_gio_hang_trong_bao_loi(self):
        with self.assertRaises(ValidationError) as ctx:
            services.place_order(self.user, address_id=self.addr.pk)
        self.assertEqual(ctx.exception.code, "empty_cart")
        self.assertEqual(Order.objects.count(), 0)

    def test_hai_nguoi_mua_cung_mon_cuoi_cung_nguoi_thu_hai_bi_chan(self):
        last_item = self.make_product("Figure Hiếm", price=2500000, stock=1)
        other_addr = self.make_address(user=self.other_user)
        self.add_to_user_cart(last_item, 1, user=self.user)
        self.add_to_user_cart(last_item, 1, user=self.other_user)

        # Người thứ nhất đặt thành công, kho về 0
        order1 = services.place_order(self.user, address_id=self.addr.pk)
        last_item.refresh_from_db()
        self.assertEqual(last_item.stock, 0)
        self.assertEqual(order1.total, 2530000)

        # Người thứ hai bấm đặt ngay sau đó -> báo hết hàng, không tạo đơn, kho vẫn bằng 0
        with self.assertRaises(ValidationError) as ctx:
            services.place_order(self.other_user, address_id=other_addr.pk)
        self.assertEqual(ctx.exception.code, "out_of_stock")
        last_item.refresh_from_db()
        self.assertEqual(last_item.stock, 0)
        self.assertEqual(Order.objects.filter(user=self.other_user).count(), 0)

    def test_mot_mon_vuot_ton_kho_giua_chung_thi_rollback_toan_bo(self):
        self.add_to_user_cart(self.p1, 2)
        self.add_to_user_cart(self.p2, 3)
        # Giữa chừng p2 chỉ còn 1 món trong kho
        self.p2.stock = 1
        self.p2.save()

        with self.assertRaises(ValidationError) as ctx:
            services.place_order(self.user, address_id=self.addr.pk)
        self.assertEqual(ctx.exception.code, "exceeds_stock")

        # p1 không bị trừ kho, đơn không được tạo, giỏ vẫn giữ nguyên
        self.p1.refresh_from_db()
        self.p2.refresh_from_db()
        self.assertEqual(self.p1.stock, 5)
        self.assertEqual(self.p2.stock, 1)
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(
            DbCartStore(self.user).quantities(), {self.p1.pk: 2, self.p2.pk: 3}
        )

    def test_san_pham_bi_an_hoac_xoa_giua_chung_bao_loi_va_rollback(self):
        self.add_to_user_cart(self.p1, 1)
        self.add_to_user_cart(self.p2, 1)
        self.p2.is_active = False
        self.p2.save()

        with self.assertRaises(ValidationError) as ctx:
            services.place_order(self.user, address_id=self.addr.pk)
        self.assertEqual(ctx.exception.code, "product_unavailable")
        self.p1.refresh_from_db()
        self.assertEqual(self.p1.stock, 5)
        self.assertEqual(Order.objects.count(), 0)

    def test_dung_dia_chi_cua_nguoi_khac_bi_tu_choi(self):
        other_addr = self.make_address(user=self.other_user)
        self.add_to_user_cart(self.p1, 1)

        with self.assertRaises(ValidationError) as ctx:
            services.place_order(self.user, address_id=other_addr.pk)
        self.assertEqual(ctx.exception.code, "invalid_address")
        self.assertEqual(Order.objects.count(), 0)

    def test_dia_chi_nhap_tay_thieu_hoac_sdt_sai_bi_tu_choi(self):
        self.add_to_user_cart(self.p1, 1)
        with self.assertRaises(ValidationError):
            services.place_order(
                self.user,
                receiver="",
                phone="0901234567",
                street="123 Lê Lợi",
                ward="Phường 1",
                district="Quận 1",
                province="TP.HCM",
            )
        with self.assertRaises(ValidationError):
            services.place_order(
                self.user,
                receiver="Nguyễn Văn A",
                phone="12345",
                street="123 Lê Lợi",
                ward="Phường 1",
                district="Quận 1",
                province="TP.HCM",
            )
        self.assertEqual(Order.objects.count(), 0)

    def test_gia_doi_truoc_khi_checkout_thi_don_hang_luu_gia_moi_nhat(self):
        self.add_to_user_cart(self.p1, 2)
        self.p1.price = 1800000
        self.p1.save()

        order = services.place_order(self.user, address_id=self.addr.pk)
        self.assertEqual(order.total, 3630000)
        self.assertEqual(OrderItem.objects.get(order=order).unit_price, 1800000)


class CheckoutViewTests(CheckoutBase):
    def setUp(self):
        self.p1 = self.make_product("Luffy", price=1500000, stock=5)
        self.addr = self.make_address()

    def login(self, user=None):
        self.client.login(email=(user or self.user).email, password=PASSWORD)

    def test_chua_dang_nhap_bi_chuyen_ve_login(self):
        resp = self.client.get(reverse("orders:checkout"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("accounts:login"), resp["Location"])

    def test_gio_trong_vao_checkout_chuyen_ve_gio_hang(self):
        self.login()
        resp = self.client.get(reverse("orders:checkout"), follow=True)
        self.assertRedirects(resp, reverse("carts:cart"))
        self.assertContains(resp, "Giỏ hàng của bạn đang trống")

    def test_gio_co_san_pham_het_hang_vao_checkout_chuyen_ve_gio_hang(self):
        self.login()
        self.add_to_user_cart(self.p1, 2)
        self.p1.stock = 0
        self.p1.save()
        resp = self.client.get(reverse("orders:checkout"), follow=True)
        self.assertRedirects(resp, reverse("carts:cart"))
        self.assertContains(resp, "không thể đặt")

    def test_hien_trang_checkout_voi_dia_chi_mac_dinh(self):
        self.login()
        self.add_to_user_cart(self.p1, 2)
        resp = self.client.get(reverse("orders:checkout"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Luffy")
        self.assertContains(resp, "3.000.000 ₫")
        self.assertContains(resp, "Nguyễn Văn A")
        self.assertContains(resp, "123 Lê Lợi")
        self.assertNotContains(resp, "Quận / Huyện")

    def test_post_dat_hang_bang_so_dia_chi_thanh_cong(self):
        self.login()
        self.add_to_user_cart(self.p1, 2)
        resp = self.client.post(
            reverse("orders:checkout"),
            {"address_id": self.addr.pk, "note": "Gói kỹ giúp mình"},
        )
        order = Order.objects.get(user=self.user)
        self.assertRedirects(
            resp, reverse("orders:success", kwargs={"order_id": order.pk})
        )
        self.p1.refresh_from_db()
        self.assertEqual(self.p1.stock, 3)
        self.assertEqual(CartItem.objects.filter(cart__user=self.user).count(), 0)

        success_page = self.client.get(
            reverse("orders:success", kwargs={"order_id": order.pk})
        )
        self.assertEqual(success_page.status_code, 200)
        self.assertContains(success_page, f"#{order.pk}")
        self.assertContains(success_page, "Luffy")
        self.assertContains(success_page, "3.000.000 ₫")

    def test_post_dat_hang_bang_dia_chi_nhap_moi(self):
        self.login()
        self.add_to_user_cart(self.p1, 1)
        resp = self.client.post(
            reverse("orders:checkout"),
            {
                "address_id": "",
                "receiver": "Lê Văn C",
                "phone": "0987654321",
                "street": "10 Hai Bà Trưng",
                "ward": "Phường 6",
                "province": "TP. Hồ Chí Minh",
                "note": "",
            },
        )
        order = Order.objects.get(user=self.user)
        self.assertRedirects(
            resp, reverse("orders:success", kwargs={"order_id": order.pk})
        )
        self.assertEqual(order.receiver, "Lê Văn C")

    def test_post_het_hang_giua_chung_chuyen_ve_gio_hang_kem_loi(self):
        self.login()
        self.add_to_user_cart(self.p1, 2)
        self.p1.stock = 1
        self.p1.save()

        resp = self.client.post(
            reverse("orders:checkout"),
            {"address_id": self.addr.pk},
            follow=True,
        )
        self.assertRedirects(resp, reverse("carts:cart"))
        self.assertContains(resp, "Chỉ còn 1")
        self.assertEqual(Order.objects.count(), 0)

    def test_khong_xem_duoc_trang_thanh_cong_cua_nguoi_khac(self):
        self.add_to_user_cart(self.p1, 1)
        order = services.place_order(self.user, address_id=self.addr.pk)

        self.login(self.other_user)
        resp = self.client.get(
            reverse("orders:success", kwargs={"order_id": order.pk})
        )
        self.assertEqual(resp.status_code, 404)
        self.assertIsNone(selectors.get_user_order(self.other_user, order.pk))
