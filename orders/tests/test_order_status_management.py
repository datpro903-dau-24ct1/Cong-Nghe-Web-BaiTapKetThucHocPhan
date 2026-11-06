"""CN16: Quản lý đơn hàng — đổi trạng thái (chờ → xác nhận → giao → hoàn tất / hủy) + lịch sử."""
from django.core.exceptions import ValidationError
from django.urls import reverse

from accounts.models import User
from orders import services
from orders.models import Order, OrderStatusLog
from orders.tests.test_checkout import CheckoutBase, PASSWORD


class OrderStatusTransitionServiceTests(CheckoutBase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.staff = User.objects.create_superuser(
            "admin@example.com", PASSWORD, full_name="Quản trị viên"
        )

    def setUp(self):
        self.p1 = self.make_product("Luffy Gear 5", price=1500000, stock=5)
        self.p2 = self.make_product("Zoro Wano", price=1000000, stock=4)
        self.addr = self.make_address()

    def make_sample_order(self):
        self.add_to_user_cart(self.p1, 2)
        self.add_to_user_cart(self.p2, 1)
        return services.place_order(self.user, address_id=self.addr.pk)

    def test_chuyen_trang_thai_dung_thu_tu_va_ghi_lich_su_day_du(self):
        order = self.make_sample_order()
        self.assertEqual(order.status, Order.Status.PENDING)

        services.transition_order_status(
            order.pk, Order.Status.CONFIRMED, actor=self.staff, note="Đã gọi xác nhận"
        )
        services.transition_order_status(
            order.pk, Order.Status.SHIPPING, actor=self.staff, note="Bàn giao GHN"
        )
        services.transition_order_status(
            order.pk, Order.Status.COMPLETED, actor=self.staff, note="Khách đã nhận"
        )

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.COMPLETED)

        logs = list(OrderStatusLog.objects.filter(order=order))
        self.assertEqual(len(logs), 3)
        self.assertEqual(
            [(l.from_status, l.to_status, l.changed_by_id, l.note) for l in logs],
            [
                (
                    Order.Status.PENDING,
                    Order.Status.CONFIRMED,
                    self.staff.pk,
                    "Đã gọi xác nhận",
                ),
                (
                    Order.Status.CONFIRMED,
                    Order.Status.SHIPPING,
                    self.staff.pk,
                    "Bàn giao GHN",
                ),
                (
                    Order.Status.SHIPPING,
                    Order.Status.COMPLETED,
                    self.staff.pk,
                    "Khách đã nhận",
                ),
            ],
        )

    def test_chuyen_trang_thai_sai_thu_tu_bi_chan_va_khong_ghi_log(self):
        order = self.make_sample_order()

        # Từ pending không được nhảy cóc sang shipping hoặc completed, hoặc tự chuyển sang chính nó
        for invalid_target in (
            Order.Status.PENDING,
            Order.Status.SHIPPING,
            Order.Status.COMPLETED,
        ):
            with self.assertRaises(ValidationError) as ctx:
                services.transition_order_status(
                    order.pk, invalid_target, actor=self.staff
                )
            self.assertEqual(
                ctx.exception.code, "invalid_status_transition", invalid_target
            )

        # Sang confirmed rồi không được lùi về pending hay nhảy cóc sang completed
        services.transition_order_status(
            order.pk, Order.Status.CONFIRMED, actor=self.staff
        )
        for invalid_target in (Order.Status.PENDING, Order.Status.COMPLETED):
            with self.assertRaises(ValidationError) as ctx:
                services.transition_order_status(
                    order.pk, invalid_target, actor=self.staff
                )
            self.assertEqual(
                ctx.exception.code, "invalid_status_transition", invalid_target
            )

        # Sang shipping rồi không được lùi về confirmed/pending hay hủy
        services.transition_order_status(
            order.pk, Order.Status.SHIPPING, actor=self.staff
        )
        for invalid_target in (
            Order.Status.PENDING,
            Order.Status.CONFIRMED,
            Order.Status.CANCELLED,
        ):
            with self.assertRaises(ValidationError) as ctx:
                services.transition_order_status(
                    order.pk, invalid_target, actor=self.staff
                )
            self.assertEqual(
                ctx.exception.code, "invalid_status_transition", invalid_target
            )

        self.assertEqual(OrderStatusLog.objects.filter(order=order).count(), 2)

    def test_huy_don_da_hoan_tat_bi_chan_va_khong_hoan_ton_kho(self):
        order = self.make_sample_order()
        services.transition_order_status(
            order.pk, Order.Status.CONFIRMED, actor=self.staff
        )
        services.transition_order_status(
            order.pk, Order.Status.SHIPPING, actor=self.staff
        )
        services.transition_order_status(
            order.pk, Order.Status.COMPLETED, actor=self.staff
        )

        with self.assertRaises(ValidationError) as ctx:
            services.transition_order_status(
                order.pk, Order.Status.CANCELLED, actor=self.staff
            )
        self.assertEqual(ctx.exception.code, "invalid_status_transition")

        order.refresh_from_db()
        self.p1.refresh_from_db()
        self.assertEqual(order.status, Order.Status.COMPLETED)
        self.assertEqual(self.p1.stock, 3)

    def test_admin_huy_don_o_trang_thai_confirmed_hoan_lai_ton_kho_va_ghi_log(self):
        order = self.make_sample_order()  # p1: 5->3, p2: 4->3
        services.transition_order_status(
            order.pk, Order.Status.CONFIRMED, actor=self.staff
        )

        services.transition_order_status(
            order.pk,
            Order.Status.CANCELLED,
            actor=self.staff,
            note="Khách báo đổi ý qua điện thoại",
        )

        order.refresh_from_db()
        self.p1.refresh_from_db()
        self.p2.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(self.p1.stock, 5)
        self.assertEqual(self.p2.stock, 4)

        last_log = OrderStatusLog.objects.filter(order=order).last()
        self.assertEqual(last_log.from_status, Order.Status.CONFIRMED)
        self.assertEqual(last_log.to_status, Order.Status.CANCELLED)
        self.assertEqual(last_log.changed_by, self.staff)

        # Đơn đã hủy không được chuyển sang trạng thái khác hay hủy lần 2
        with self.assertRaises(ValidationError) as ctx:
            services.transition_order_status(
                order.pk, Order.Status.CONFIRMED, actor=self.staff
            )
        self.assertEqual(ctx.exception.code, "invalid_status_transition")

    def test_khach_tu_huy_don_cung_ghi_lich_su_order_status_log(self):
        order = self.make_sample_order()
        services.cancel_order(self.user, order.pk)

        log = OrderStatusLog.objects.get(order=order)
        self.assertEqual(log.from_status, Order.Status.PENDING)
        self.assertEqual(log.to_status, Order.Status.CANCELLED)
        self.assertEqual(log.changed_by, self.user)


class OrderAdminManagementTests(CheckoutBase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.staff = User.objects.create_superuser(
            "admin@example.com", PASSWORD, full_name="Quản trị viên"
        )

    def setUp(self):
        self.p1 = self.make_product("Luffy Gear 5", price=1500000, stock=5)
        self.addr = self.make_address()
        self.client.force_login(self.staff)

    def make_sample_order(self):
        self.add_to_user_cart(self.p1, 2)
        return services.place_order(self.user, address_id=self.addr.pk)

    def _admin_post_payload(self, order, new_status):
        return {
            "status": new_status,
            "note": order.note,
            "items-TOTAL_FORMS": 0,
            "items-INITIAL_FORMS": 0,
            "items-MIN_NUM_FORMS": 0,
            "items-MAX_NUM_FORMS": 0,
            "status_logs-TOTAL_FORMS": 0,
            "status_logs-INITIAL_FORMS": 0,
            "status_logs-MIN_NUM_FORMS": 0,
            "status_logs-MAX_NUM_FORMS": 0,
        }

    def test_danh_sach_va_chi_tiet_don_hang_trong_admin(self):
        order = self.make_sample_order()
        list_resp = self.client.get("/admin/orders/order/")
        self.assertEqual(list_resp.status_code, 200)
        self.assertContains(list_resp, "Nguyễn Văn A")

        change_resp = self.client.get(f"/admin/orders/order/{order.pk}/change/")
        self.assertEqual(change_resp.status_code, 200)
        self.assertContains(change_resp, "Luffy Gear 5")

    def test_admin_doi_trang_thai_hop_le_ghi_lich_su(self):
        order = self.make_sample_order()
        change_url = f"/admin/orders/order/{order.pk}/change/"

        resp = self.client.post(
            change_url, self._admin_post_payload(order, Order.Status.CONFIRMED)
        )
        self.assertEqual(resp.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CONFIRMED)
        self.assertEqual(OrderStatusLog.objects.filter(order=order).count(), 1)

    def test_admin_doi_trang_thai_sai_thu_tu_bi_bao_loi_tren_form(self):
        order = self.make_sample_order()
        change_url = f"/admin/orders/order/{order.pk}/change/"

        resp = self.client.post(
            change_url, self._admin_post_payload(order, Order.Status.COMPLETED)
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Không thể chuyển trạng thái")
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertEqual(OrderStatusLog.objects.filter(order=order).count(), 0)

    def test_admin_huy_don_hoan_lai_ton_kho(self):
        order = self.make_sample_order()  # stock 5 -> 3
        change_url = f"/admin/orders/order/{order.pk}/change/"

        resp = self.client.post(
            change_url, self._admin_post_payload(order, Order.Status.CANCELLED)
        )
        self.assertEqual(resp.status_code, 302)
        order.refresh_from_db()
        self.p1.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(self.p1.stock, 5)

    def test_nhan_vien_is_staff_khong_can_superuser_van_doi_duoc_trang_thai_don(self):
        employee = User.objects.create_user(
            "nv@example.com", PASSWORD, full_name="Nhân Viên", is_staff=True
        )
        order = self.make_sample_order()
        self.client.force_login(employee)

        self.assertEqual(self.client.get("/admin/orders/order/").status_code, 200)
        change_url = f"/admin/orders/order/{order.pk}/change/"
        self.assertEqual(self.client.get(change_url).status_code, 200)

        resp = self.client.post(
            change_url, self._admin_post_payload(order, Order.Status.CONFIRMED)
        )
        self.assertEqual(resp.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CONFIRMED)
