"""CN13: Thanh toán COD + phí vận chuyển + làm tròn tiền + chống submit trùng."""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.urls import reverse

from orders import services
from orders.models import Order
from orders.tests.test_checkout import CheckoutBase, PASSWORD


class ShippingFeeAndRoundingTests(CheckoutBase):
    def setUp(self):
        self.p1 = self.make_product("Luffy", price=1500000, stock=5)

    def test_phi_van_chuyen_noi_thanh_hcm_va_ha_noi_la_30000(self):
        for province in (
            "TP. Hồ Chí Minh",
            "TP.HCM",
            "Hồ Chí Minh",
            "Hà Nội",
            "Thành phố Hà Nội",
        ):
            self.assertEqual(
                services.calculate_shipping_fee(province),
                Decimal(30000),
                province,
            )

    def test_phi_van_chuyen_tinh_thanh_khac_la_40000(self):
        for province in ("Đà Nẵng", "Cần Thơ", "Bình Dương", "Tỉnh Khánh Hòa", "Hải Phòng"):
            self.assertEqual(
                services.calculate_shipping_fee(province),
                Decimal(40000),
                province,
            )

    def test_dia_chi_ngoai_vung_giao_bao_loi(self):
        for invalid_province in ("Tokyo", "California", "Quốc tế", "Sao Hỏa", ""):
            with self.assertRaises(ValidationError) as ctx:
                services.calculate_shipping_fee(invalid_province)
            self.assertEqual(ctx.exception.code, "out_of_delivery_area")

    def test_dat_hang_voi_dia_chi_ngoai_vung_giao_bi_chan_va_khong_tru_kho(self):
        self.add_to_user_cart(self.p1, 2)
        with self.assertRaises(ValidationError) as ctx:
            services.place_order(
                self.user,
                receiver="Nguyễn Văn A",
                phone="0901234567",
                street="123 Shibuya",
                ward="Ward 1",
                district="Shibuya",
                province="Tokyo",
            )
        self.assertEqual(ctx.exception.code, "out_of_delivery_area")
        self.p1.refresh_from_db()
        self.assertEqual(self.p1.stock, 5)
        self.assertEqual(Order.objects.count(), 0)

    def test_dat_hang_tinh_dung_phi_ship_ngoai_tinh_va_cod(self):
        addr = self.make_address(province="Đà Nẵng")
        self.add_to_user_cart(self.p1, 2)  # 3.000.000

        order = services.place_order(self.user, address_id=addr.pk)
        self.assertEqual(order.payment_method, Order.PaymentMethod.COD)
        self.assertEqual(order.subtotal, Decimal(3000000))
        self.assertEqual(order.shipping_fee, Decimal(40000))
        self.assertEqual(order.total, Decimal(3040000))

    def test_phuong_thuc_thanh_toan_khong_hop_le_bi_tu_choi(self):
        addr = self.make_address()
        self.add_to_user_cart(self.p1, 1)
        with self.assertRaises(ValidationError) as ctx:
            services.place_order(
                self.user, address_id=addr.pk, payment_method="bitcoin"
            )
        self.assertEqual(ctx.exception.code, "invalid_payment_method")
        self.assertEqual(Order.objects.count(), 0)

    def test_lam_tron_tien_chuan_khong_lech_tong(self):
        self.assertEqual(services.quantize_vnd(Decimal("30000.4")), Decimal(30000))
        self.assertEqual(services.quantize_vnd(Decimal("30000.5")), Decimal(30001))
        self.assertEqual(services.quantize_vnd("1500000"), Decimal(1500000))

        addr = self.make_address()
        self.add_to_user_cart(self.p1, 1)
        order = services.place_order(
            self.user, address_id=addr.pk, shipping_fee=Decimal("30000.5")
        )
        self.assertEqual(order.shipping_fee, Decimal(30001))
        self.assertEqual(order.total, order.subtotal + order.shipping_fee)
        self.assertEqual(order.total, Decimal(1530001))


class DoubleSubmitCheckoutViewTests(CheckoutBase):
    def setUp(self):
        self.p1 = self.make_product("Luffy", price=1500000, stock=5)
        self.addr = self.make_address()
        self.client.login(email=self.user.email, password=PASSWORD)

    def test_bam_dat_hang_hai_lan_voi_cung_checkout_token_chi_tao_mot_don(self):
        self.add_to_user_cart(self.p1, 2)
        get_resp = self.client.get(reverse("orders:checkout"))
        token = get_resp.context["form"]["checkout_token"].value()
        self.assertTrue(token)

        payload = {
            "address_id": self.addr.pk,
            "payment_method": Order.PaymentMethod.COD,
            "checkout_token": token,
            "note": "Đặt 1 lần",
        }
        resp1 = self.client.post(reverse("orders:checkout"), payload)
        order = Order.objects.get(user=self.user)
        expected_url = reverse("orders:success", kwargs={"order_id": order.pk})
        self.assertRedirects(resp1, expected_url)

        # Bấm lần 2 với cùng form payload (double submit): vẫn về đúng trang thành công, không tạo đơn mới
        resp2 = self.client.post(reverse("orders:checkout"), payload)
        self.assertRedirects(resp2, expected_url)
        self.assertEqual(Order.objects.filter(user=self.user).count(), 1)
        self.p1.refresh_from_db()
        self.assertEqual(self.p1.stock, 3)

    def test_trang_checkout_va_thanh_cong_hien_thi_phi_van_chuyen_va_cod(self):
        self.add_to_user_cart(self.p1, 2)  # 3.000.000 + 30.000 ship = 3.030.000
        resp = self.client.get(reverse("orders:checkout"))
        self.assertContains(resp, "Thanh toán khi nhận hàng (COD)")
        self.assertContains(resp, "30.000 ₫")
        self.assertContains(resp, "3.030.000 ₫")

        post_resp = self.client.post(
            reverse("orders:checkout"),
            {"address_id": self.addr.pk, "payment_method": "cod"},
            follow=True,
        )
        self.assertContains(post_resp, "30.000 ₫")
        self.assertContains(post_resp, "3.030.000 ₫")

    def test_post_dia_chi_ngoai_vung_giao_hien_loi_tren_form_checkout(self):
        self.add_to_user_cart(self.p1, 1)
        resp = self.client.post(
            reverse("orders:checkout"),
            {
                "address_id": "",
                "receiver": "Nguyễn Văn A",
                "phone": "0901234567",
                "street": "123 Shibuya",
                "ward": "Ward 1",
                "province": "Tokyo",
                "payment_method": "cod",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "ngoài vùng giao hàng")
        self.assertEqual(Order.objects.count(), 0)
