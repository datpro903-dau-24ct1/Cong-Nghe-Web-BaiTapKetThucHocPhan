from decimal import Decimal

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from accounts.models import User
from catalog import selectors, services
from catalog.models import Review
from orders.models import Order, OrderItem


class ReviewBaseTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = services.create_category("Scale Figure")
        cls.series = services.create_series("One Piece")
        cls.brand = services.create_brand("Good Smile Company")
        cls.product = services.create_product(
            name="Luffy Gear 5",
            category=cls.category,
            series=cls.series,
            brand=cls.brand,
            price=1500000,
            stock=10,
        )
        cls.other_product = services.create_product(
            name="Zoro Enma",
            category=cls.category,
            series=cls.series,
            brand=cls.brand,
            price=1200000,
            stock=5,
        )
        cls.buyer = User.objects.create_user(
            email="buyer@example.com",
            password="Password123!",
            full_name="Người Mua Một",
        )
        cls.buyer2 = User.objects.create_user(
            email="buyer2@example.com",
            password="Password123!",
            full_name="Người Mua Hai",
        )
        cls.non_buyer = User.objects.create_user(
            email="stranger@example.com",
            password="Password123!",
            full_name="Khách Chưa Mua",
        )

    def create_order_with_product(self, user, product=None, status=Order.Status.COMPLETED):
        product = product or self.product
        order = Order.objects.create(
            user=user,
            receiver=user.full_name,
            phone="0901234567",
            street="123 Lê Lợi",
            ward="Phường Bến Nghé",
            district="Quận 1",
            province="TP. Hồ Chí Minh",
            status=status,
            subtotal=product.price,
            shipping_fee=0,
            total=product.price,
        )
        OrderItem.objects.create(
            order=order,
            product=product,
            product_name=product.name,
            unit_price=product.price,
            quantity=1,
        )
        return order


class ReviewModelAndServiceTests(ReviewBaseTestCase):
    def test_nguoi_da_mua_tao_danh_gia_thanh_cong_va_cap_nhat_diem_trung_binh(self):
        self.create_order_with_product(self.buyer)
        self.create_order_with_product(self.buyer2)

        r1 = services.create_review(
            user=self.buyer,
            product=self.product,
            rating=5,
            comment="Mô hình sơn cực nét!",
        )
        self.assertEqual(r1.rating, 5)
        self.assertEqual(r1.comment, "Mô hình sơn cực nét!")

        self.product.refresh_from_db()
        self.assertEqual(self.product.review_count, 1)
        self.assertEqual(self.product.rating_avg, Decimal("5.00"))

        services.create_review(
            user=self.buyer2,
            product=self.product,
            rating=4,
            comment="Đóng gói kỹ.",
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.review_count, 2)
        self.assertEqual(self.product.rating_avg, Decimal("4.50"))

    def test_chan_nguoi_chua_mua_danh_gia(self):
        with self.assertRaises(ValidationError) as ctx:
            services.create_review(
                user=self.non_buyer,
                product=self.product,
                rating=5,
                comment="Chưa mua nhưng muốn đánh giá",
            )
        self.assertEqual(ctx.exception.code, "not_purchased")
        self.assertEqual(Review.objects.count(), 0)

    def test_don_hang_da_huy_khong_duoc_tinh_la_da_mua(self):
        self.create_order_with_product(
            self.non_buyer, status=Order.Status.CANCELLED
        )
        self.assertFalse(selectors.has_purchased_product(self.non_buyer, self.product))
        self.assertFalse(selectors.can_user_review_product(self.non_buyer, self.product))
        with self.assertRaises(ValidationError) as ctx:
            services.create_review(
                user=self.non_buyer,
                product=self.product,
                rating=4,
                comment="Đơn đã hủy",
            )
        self.assertEqual(ctx.exception.code, "not_purchased")

    def test_chan_khach_chua_dang_nhap_danh_gia(self):
        for anon in (None, AnonymousUser()):
            with self.assertRaises(ValidationError) as ctx:
                services.create_review(
                    user=anon,
                    product=self.product,
                    rating=5,
                    comment="Ẩn danh",
                )
            self.assertEqual(ctx.exception.code, "unauthenticated")

    def test_chan_danh_gia_trung_o_tang_service_va_db(self):
        self.create_order_with_product(self.buyer)
        services.create_review(
            user=self.buyer,
            product=self.product,
            rating=5,
            comment="Lần 1",
        )
        self.assertFalse(selectors.can_user_review_product(self.buyer, self.product))

        with self.assertRaises(ValidationError) as ctx:
            services.create_review(
                user=self.buyer,
                product=self.product,
                rating=3,
                comment="Lần 2",
            )
        self.assertEqual(ctx.exception.code, "duplicate_review")
        self.assertEqual(Review.objects.count(), 1)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Review.objects.create(
                    product=self.product,
                    user=self.buyer,
                    rating=4,
                    comment="Trực tiếp DB",
                )

    def test_chan_diem_ngoai_khoang_1_den_5(self):
        self.create_order_with_product(self.buyer)
        for bad_rating in (0, -1, 6, 10, "abc", None, True, False, 3.5):
            with self.assertRaises(ValidationError) as ctx:
                services.create_review(
                    user=self.buyer,
                    product=self.product,
                    rating=bad_rating,
                    comment="Điểm sai",
                )
            self.assertEqual(ctx.exception.code, "invalid_rating")
        self.assertEqual(Review.objects.count(), 0)


class ReviewViewAndTemplateTests(ReviewBaseTestCase):
    def test_khach_chua_dang_nhap_post_danh_gia_chuyen_huong_login(self):
        url = reverse("submit_review", args=[self.product.slug])
        resp = self.client.post(url, {"rating": 5, "comment": "Tốt"})
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("accounts:login"), resp["Location"])

    def test_nguoi_da_mua_gui_danh_gia_qua_form_thanh_cong(self):
        self.create_order_with_product(self.buyer)
        self.client.force_login(self.buyer)

        detail_url = reverse("product_detail", args=[self.product.slug])
        resp_get = self.client.get(detail_url)
        self.assertTrue(resp_get.context["can_review"])
        self.assertContains(resp_get, "Gửi đánh giá")

        submit_url = reverse("submit_review", args=[self.product.slug])
        resp_post = self.client.post(
            submit_url,
            {"rating": 5, "comment": "Rất đáng tiền!"},
            follow=True,
        )
        self.assertEqual(resp_post.status_code, 200)
        self.assertContains(resp_post, "Cảm ơn bạn đã đánh giá sản phẩm")
        self.assertContains(resp_post, "Rất đáng tiền!")
        self.assertContains(resp_post, "Người Mua Một")
        self.assertFalse(resp_post.context["can_review"])

    def test_nguoi_chua_mua_gui_post_bi_tu_choi(self):
        self.client.force_login(self.non_buyer)
        submit_url = reverse("submit_review", args=[self.product.slug])
        resp = self.client.post(
            submit_url,
            {"rating": 5, "comment": "Hack review"},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Bạn cần mua sản phẩm này trước khi đánh giá")
        self.assertEqual(Review.objects.count(), 0)

    def test_gui_danh_gia_trung_qua_post_bao_loi(self):
        self.create_order_with_product(self.buyer)
        services.create_review(
            user=self.buyer, product=self.product, rating=5, comment="Đánh giá đầu"
        )
        self.client.force_login(self.buyer)
        submit_url = reverse("submit_review", args=[self.product.slug])
        resp = self.client.post(
            submit_url,
            {"rating": 4, "comment": "Đánh giá trùng"},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Bạn đã đánh giá sản phẩm này rồi")
        self.assertEqual(Review.objects.count(), 1)

    def test_gui_diem_ngoai_1_5_qua_post_bao_loi(self):
        self.create_order_with_product(self.buyer)
        self.client.force_login(self.buyer)
        submit_url = reverse("submit_review", args=[self.product.slug])
        for bad in ("0", "6", "-2", "abc"):
            resp = self.client.post(
                submit_url,
                {"rating": bad, "comment": "Điểm lỗi"},
                follow=True,
            )
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(Review.objects.count(), 0)

    def test_noi_dung_binh_luan_chua_html_script_bi_escape_chong_xss(self):
        self.create_order_with_product(self.buyer)
        xss_payload = "<script>alert('xss')</script><img src=x onerror=alert(1)>"
        services.create_review(
            user=self.buyer,
            product=self.product,
            rating=5,
            comment=xss_payload,
        )
        resp = self.client.get(reverse("product_detail", args=[self.product.slug]))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "<script>alert('xss')</script>")
        self.assertNotContains(resp, "<img src=x onerror=alert(1)>")
        self.assertContains(resp, "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;")

    def test_trang_chi_tiet_khong_tang_so_query_khi_chua_co_danh_gia(self):
        url = reverse("product_detail", args=[self.product.slug])
        with CaptureQueriesContext(connection) as queries:
            resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(queries), 5)
