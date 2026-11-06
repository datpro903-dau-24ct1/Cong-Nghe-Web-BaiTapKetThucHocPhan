"""CN14: Lịch sử đơn hàng + chi tiết đơn + hủy đơn (kiểm tra quyền sở hữu & hoàn tồn kho)."""
from django.core.exceptions import ValidationError
from django.test import Client
from django.urls import reverse

from orders import selectors, services
from orders.models import Order
from orders.tests.test_checkout import CheckoutBase, PASSWORD


class CancelOrderServiceTests(CheckoutBase):
    def setUp(self):
        self.p1 = self.make_product("Luffy", price=1500000, stock=5)
        self.p2 = self.make_product("Zoro", price=1000000, stock=4)
        self.addr = self.make_address()

    def create_sample_order(self, user=None, addr=None):
        target_user = user or self.user
        target_addr = addr or self.addr
        self.add_to_user_cart(self.p1, 2, user=target_user)
        self.add_to_user_cart(self.p2, 1, user=target_user)
        return services.place_order(target_user, address_id=target_addr.pk)

    def test_huy_don_pending_thanh_cong_va_hoan_lai_ton_kho(self):
        order = self.create_sample_order()
        self.p1.refresh_from_db()
        self.p2.refresh_from_db()
        self.assertEqual(self.p1.stock, 3)
        self.assertEqual(self.p2.stock, 3)

        cancelled = services.cancel_order(self.user, order.pk)
        self.assertEqual(cancelled.status, Order.Status.CANCELLED)

        order.refresh_from_db()
        self.p1.refresh_from_db()
        self.p2.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(self.p1.stock, 5)
        self.assertEqual(self.p2.stock, 4)

    def test_khong_cho_huy_don_da_giao_hoac_dang_giao_hoac_da_xac_nhan(self):
        order = self.create_sample_order()
        self.p1.refresh_from_db()
        stock_before = self.p1.stock

        for status in (
            Order.Status.CONFIRMED,
            Order.Status.SHIPPING,
            Order.Status.COMPLETED,
        ):
            order.status = status
            order.save(update_fields=["status"])

            with self.assertRaises(ValidationError) as ctx:
                services.cancel_order(self.user, order.pk)
            self.assertEqual(ctx.exception.code, "cannot_cancel", status)

            order.refresh_from_db()
            self.p1.refresh_from_db()
            self.assertEqual(order.status, status)
            self.assertEqual(self.p1.stock, stock_before)

    def test_huy_don_hai_lan_khong_cong_ton_kho_lan_hai(self):
        order = self.create_sample_order()
        services.cancel_order(self.user, order.pk)

        with self.assertRaises(ValidationError) as ctx:
            services.cancel_order(self.user, order.pk)
        self.assertEqual(ctx.exception.code, "already_cancelled")

        self.p1.refresh_from_db()
        self.p2.refresh_from_db()
        self.assertEqual(self.p1.stock, 5)
        self.assertEqual(self.p2.stock, 4)

    def test_khong_cho_huy_don_cua_nguoi_khac(self):
        order = self.create_sample_order()
        with self.assertRaises(ValidationError) as ctx:
            services.cancel_order(self.other_user, order.pk)
        self.assertEqual(ctx.exception.code, "order_not_found")

        order.refresh_from_db()
        self.p1.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertEqual(self.p1.stock, 3)

    def test_huy_don_co_san_pham_da_bi_xoa_van_hoan_kho_san_pham_con_lai(self):
        order = self.create_sample_order()
        self.p2.delete()

        services.cancel_order(self.user, order.pk)
        order.refresh_from_db()
        self.p1.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(self.p1.stock, 5)


class OrderHistoryAndDetailViewTests(CheckoutBase):
    def setUp(self):
        self.p1 = self.make_product("Luffy Gear 5", price=1500000, stock=6)
        self.addr = self.make_address()
        self.other_addr = self.make_address(user=self.other_user)

    def login(self, user=None):
        self.client.login(email=(user or self.user).email, password=PASSWORD)

    def place_one(self, user=None, addr=None, quantity=1):
        target_user = user or self.user
        target_addr = addr or self.addr
        self.add_to_user_cart(self.p1, quantity, user=target_user)
        return services.place_order(target_user, address_id=target_addr.pk)

    def test_chua_dang_nhap_bi_chuyen_ve_login(self):
        for url in (
            reverse("orders:list"),
            reverse("orders:detail", kwargs={"order_id": 1}),
        ):
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 302)
            self.assertIn(reverse("accounts:login"), resp["Location"])

    def test_danh_sach_don_hang_chi_hien_don_cua_minh_theo_thu_tu_moi_nhat(self):
        o1 = self.place_one(user=self.user, addr=self.addr, quantity=1)
        other_order = self.place_one(
            user=self.other_user, addr=self.other_addr, quantity=1
        )
        o2 = self.place_one(user=self.user, addr=self.addr, quantity=2)

        self.login(self.user)
        resp = self.client.get(reverse("orders:list"))
        self.assertEqual(resp.status_code, 200)
        orders_in_page = [o.pk for o in resp.context["page_obj"].object_list]
        self.assertEqual(orders_in_page, [o2.pk, o1.pk])
        self.assertNotIn(other_order.pk, orders_in_page)

    def test_xem_chi_tiet_don_cua_minh_va_chan_xem_don_nguoi_khac(self):
        my_order = self.place_one(user=self.user, addr=self.addr, quantity=2)
        other_order = self.place_one(
            user=self.other_user, addr=self.other_addr, quantity=1
        )

        self.login(self.user)
        resp = self.client.get(
            reverse("orders:detail", kwargs={"order_id": my_order.pk})
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Luffy Gear 5")
        self.assertContains(resp, "3.030.000 ₫")
        self.assertContains(resp, "Hủy đơn hàng")

        # Đơn của người khác -> 404
        resp_other = self.client.get(
            reverse("orders:detail", kwargs={"order_id": other_order.pk})
        )
        self.assertEqual(resp_other.status_code, 404)

    def test_post_huy_don_pending_hoan_ton_kho_va_doi_trang_thai(self):
        order = self.place_one(quantity=2)  # stock từ 6 -> 4
        self.login()

        resp = self.client.post(
            reverse("orders:cancel", kwargs={"order_id": order.pk}), follow=True
        )
        self.assertRedirects(
            resp, reverse("orders:detail", kwargs={"order_id": order.pk})
        )
        self.assertContains(resp, "Đã hủy đơn hàng")
        order.refresh_from_db()
        self.p1.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(self.p1.stock, 6)

    def test_post_huy_don_da_giao_bao_loi_va_khong_hoan_kho(self):
        order = self.place_one(quantity=2)
        order.status = Order.Status.COMPLETED
        order.save(update_fields=["status"])
        self.login()

        resp = self.client.post(
            reverse("orders:cancel", kwargs={"order_id": order.pk}), follow=True
        )
        self.assertRedirects(
            resp, reverse("orders:detail", kwargs={"order_id": order.pk})
        )
        self.assertContains(resp, "Không thể hủy")
        order.refresh_from_db()
        self.p1.refresh_from_db()
        self.assertEqual(order.status, Order.Status.COMPLETED)
        self.assertEqual(self.p1.stock, 4)

    def test_post_huy_don_cua_nguoi_khac_tra_404(self):
        other_order = self.place_one(
            user=self.other_user, addr=self.other_addr, quantity=1
        )
        self.login(self.user)
        resp = self.client.post(
            reverse("orders:cancel", kwargs={"order_id": other_order.pk})
        )
        self.assertEqual(resp.status_code, 404)
        other_order.refresh_from_db()
        self.assertEqual(other_order.status, Order.Status.PENDING)

    def test_huy_don_chi_nhan_post_va_bat_buoc_csrf(self):
        order = self.place_one(quantity=1)
        self.login()
        get_resp = self.client.get(
            reverse("orders:cancel", kwargs={"order_id": order.pk})
        )
        self.assertEqual(get_resp.status_code, 405)

        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.login(email=self.user.email, password=PASSWORD)
        post_resp = csrf_client.post(
            reverse("orders:cancel", kwargs={"order_id": order.pk})
        )
        self.assertEqual(post_resp.status_code, 403)
