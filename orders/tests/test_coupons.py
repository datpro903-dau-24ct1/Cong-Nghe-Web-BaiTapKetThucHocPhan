from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts import services as account_services
from accounts.models import User
from carts import services as cart_services
from carts.stores import DbCartStore
from catalog import services as catalog_services
from orders import services
from orders.models import Coupon, Order


class CouponBaseTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = catalog_services.create_category("Scale Figure")
        cls.series = catalog_services.create_series("One Piece")
        cls.brand = catalog_services.create_brand("Good Smile Company")
        cls.product = catalog_services.create_product(
            name="Luffy Gear 5",
            category=cls.category,
            series=cls.series,
            brand=cls.brand,
            price=Decimal(1000000),
            stock=20,
        )
        cls.user = User.objects.create_user(
            email="buyer@example.com",
            password="Password123!",
            full_name="Người Mua",
            phone="0901234567",
        )
        cls.address = account_services.create_address(
            cls.user,
            receiver="Người Mua",
            phone="0901234567",
            street="123 Lê Lợi",
            ward="Phường Bến Nghé",
            district="Quận 1",
            province="TP. Hồ Chí Minh",
            is_default=True,
        )

    def add_to_cart(self, quantity=1):
        cart_services.add_item(DbCartStore(self.user), self.product.pk, quantity)


class CouponServiceTests(CouponBaseTestCase):
    def test_ap_ma_phan_tram_va_giam_toi_da_khi_dat_hang(self):
        coupon = Coupon.objects.create(
            code="ANIME15",
            discount_type=Coupon.DiscountType.PERCENT,
            discount_value=Decimal(15),
            max_discount_amount=Decimal(120000),
            min_order_amount=Decimal(500000),
        )
        self.add_to_cart(quantity=1)  # subtotal = 1.000.000, 15% = 150.000 -> trần 120.000

        order = services.place_order(
            self.user,
            address_id=self.address.pk,
            coupon_code="  anime15 ",
        )
        self.assertEqual(order.coupon, coupon)
        self.assertEqual(order.coupon_code, "ANIME15")
        self.assertEqual(order.subtotal, Decimal(1000000))
        self.assertEqual(order.discount_amount, Decimal(120000))
        self.assertEqual(order.shipping_fee, Decimal(30000))
        self.assertEqual(order.total, Decimal(910000))

        coupon.refresh_from_db()
        self.assertEqual(coupon.used_count, 1)

    def test_ap_ma_so_tien_co_dinh_khong_vuot_qua_subtotal(self):
        Coupon.objects.create(
            code="GIAM2TR",
            discount_type=Coupon.DiscountType.FIXED,
            discount_value=Decimal(2000000),
        )
        self.add_to_cart(quantity=1)  # subtotal = 1.000.000 < 2.000.000

        order = services.place_order(
            self.user,
            address_id=self.address.pk,
            coupon_code="GIAM2TR",
        )
        self.assertEqual(order.discount_amount, Decimal(1000000))
        self.assertEqual(order.total, Decimal(30000))  # chỉ còn phí ship

    def test_chan_ma_het_han_hoac_chua_den_ngay_hieu_luc(self):
        now = timezone.now()
        Coupon.objects.create(
            code="EXPIRED",
            discount_type=Coupon.DiscountType.FIXED,
            discount_value=Decimal(50000),
            valid_until=now - timedelta(minutes=1),
        )
        Coupon.objects.create(
            code="FUTURE",
            discount_type=Coupon.DiscountType.FIXED,
            discount_value=Decimal(50000),
            valid_from=now + timedelta(days=1),
        )
        self.add_to_cart(quantity=1)

        for code in ("EXPIRED", "FUTURE"):
            with self.assertRaises(ValidationError) as ctx:
                services.place_order(
                    self.user,
                    address_id=self.address.pk,
                    coupon_code=code,
                )
            self.assertEqual(ctx.exception.code, "coupon_expired")

    def test_chan_ma_vuot_so_luot_dung_va_hoan_luot_khi_huy_don(self):
        coupon = Coupon.objects.create(
            code="ONCEONLY",
            discount_type=Coupon.DiscountType.FIXED,
            discount_value=Decimal(100000),
            usage_limit=1,
        )
        self.add_to_cart(quantity=1)
        order1 = services.place_order(
            self.user,
            address_id=self.address.pk,
            coupon_code="ONCEONLY",
        )
        coupon.refresh_from_db()
        self.assertEqual(coupon.used_count, 1)

        # Đặt đơn thứ 2 với cùng mã -> vượt số lượt dùng
        self.add_to_cart(quantity=1)
        with self.assertRaises(ValidationError) as ctx:
            services.place_order(
                self.user,
                address_id=self.address.pk,
                coupon_code="ONCEONLY",
            )
        self.assertEqual(ctx.exception.code, "coupon_usage_exceeded")

        # Hủy đơn 1 -> hoàn lại lượt dùng -> đặt lại được
        services.cancel_order(self.user, order1.pk)
        coupon.refresh_from_db()
        self.assertEqual(coupon.used_count, 0)

        order2 = services.place_order(
            self.user,
            address_id=self.address.pk,
            coupon_code="ONCEONLY",
        )
        self.assertEqual(order2.discount_amount, Decimal(100000))
        coupon.refresh_from_db()
        self.assertEqual(coupon.used_count, 1)

    def test_chan_don_chua_dat_muc_toi_thieu(self):
        Coupon.objects.create(
            code="VIP3TR",
            discount_type=Coupon.DiscountType.FIXED,
            discount_value=Decimal(300000),
            min_order_amount=Decimal(3000000),
        )
        self.add_to_cart(quantity=1)  # subtotal = 1.000.000 < 3.000.000

        with self.assertRaises(ValidationError) as ctx:
            services.place_order(
                self.user,
                address_id=self.address.pk,
                coupon_code="VIP3TR",
            )
        self.assertEqual(ctx.exception.code, "coupon_min_amount_not_met")

    def test_chan_ap_nhieu_ma_cung_luc(self):
        Coupon.objects.create(
            code="MA1",
            discount_type=Coupon.DiscountType.FIXED,
            discount_value=Decimal(50000),
        )
        Coupon.objects.create(
            code="MA2",
            discount_type=Coupon.DiscountType.FIXED,
            discount_value=Decimal(50000),
        )
        self.add_to_cart(quantity=1)

        for multi in ("MA1, MA2", "MA1;MA2", "MA1 MA2", ["MA1", "MA2"]):
            with self.assertRaises(ValidationError) as ctx:
                services.place_order(
                    self.user,
                    address_id=self.address.pk,
                    coupon_code=multi,
                )
            self.assertEqual(ctx.exception.code, "multiple_coupons_not_allowed")


class CouponCheckoutViewTests(CouponBaseTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        self.coupon = Coupon.objects.create(
            code="FIG100K",
            discount_type=Coupon.DiscountType.FIXED,
            discount_value=Decimal(100000),
            min_order_amount=Decimal(500000),
        )

    def test_checkout_ap_ma_giam_gia_thanh_cong_va_hien_thi_tren_chi_tiet_don(self):
        self.add_to_cart(quantity=1)
        resp = self.client.post(
            reverse("orders:checkout"),
            {
                "address_id": str(self.address.pk),
                "payment_method": Order.PaymentMethod.COD,
                "coupon_code": "fig100k",
                "note": "Áp mã giảm 100k",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        order = Order.objects.first()
        self.assertIsNotNone(order)
        self.assertEqual(order.coupon_code, "FIG100K")
        self.assertEqual(order.discount_amount, Decimal(100000))
        self.assertEqual(order.total, Decimal(930000))
        self.assertContains(resp, "FIG100K")
        self.assertContains(resp, "100.000")

        detail_resp = self.client.get(reverse("orders:detail", args=[order.pk]))
        self.assertContains(detail_resp, "FIG100K")
        self.assertContains(detail_resp, "100.000")

    def test_checkout_bao_loi_khi_nhap_nhieu_ma_hoac_ma_sai(self):
        self.add_to_cart(quantity=1)
        resp = self.client.post(
            reverse("orders:checkout"),
            {
                "address_id": str(self.address.pk),
                "payment_method": Order.PaymentMethod.COD,
                "coupon_code": "FIG100K, OTHER",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(
            resp, "Mỗi đơn hàng chỉ được áp dụng tối đa một mã giảm giá."
        )
        self.assertEqual(Order.objects.count(), 0)
