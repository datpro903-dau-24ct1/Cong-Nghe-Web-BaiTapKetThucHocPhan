"""CN27: Kiểm thử tích hợp Giỏ hàng - Đặt hàng, Race Condition tồn kho đa luồng & Phân quyền xuyên suốt."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import threading

from django.core.exceptions import ValidationError
from django.db import connections
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse

from accounts import services as account_services
from accounts.models import User
from carts import services as cart_services
from carts.stores import DbCartStore
from catalog import services as catalog_services
from orders import services as order_services
from orders.models import Coupon, Order


class StockRaceConditionTransactionTests(TransactionTestCase):
    """Kiểm thử race condition tồn kho bằng TransactionTestCase và đa luồng đồng thời thật."""

    def setUp(self):
        self.category = catalog_services.create_category("Scale Figure")
        self.series = catalog_services.create_series("One Piece")
        self.brand = catalog_services.create_brand("Good Smile Company")

    def _create_buyer_with_cart(self, index, product, quantity=1):
        user = User.objects.create_user(
            email=f"racer{index}@example.com",
            password="Password123!",
            full_name=f"Người Mua {index}",
            phone="0901234567",
        )
        addr = account_services.create_address(
            user,
            receiver=f"Người Mua {index}",
            phone="0901234567",
            street="123 Lê Lợi",
            ward="Phường Bến Nghé",
            district="Quận 1",
            province="TP. Hồ Chí Minh",
            is_default=True,
        )
        cart_services.add_item(DbCartStore(user), product.pk, quantity)
        return user, addr

    def test_hai_luong_cung_mua_mon_cuoi_cung_chi_mot_nguoi_thanh_cong(self):
        product = catalog_services.create_product(
            name="Luffy Gear 5 Limited",
            category=self.category,
            series=self.series,
            brand=self.brand,
            price=Decimal(2000000),
            stock=1,
        )
        u1, a1 = self._create_buyer_with_cart(1, product, quantity=1)
        u2, a2 = self._create_buyer_with_cart(2, product, quantity=1)

        barrier = threading.Barrier(2)

        def worker(user, addr):
            try:
                barrier.wait(timeout=5)
                order = order_services.place_order(user, address_id=addr.pk)
                return ("ok", order.pk)
            except ValidationError as exc:
                return ("error", exc.code)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            f1 = pool.submit(worker, u1, a1)
            f2 = pool.submit(worker, u2, a2)
            results = [f1.result(), f2.result()]

        successes = [r for r in results if r[0] == "ok"]
        errors = [r for r in results if r[0] == "error"]

        self.assertEqual(len(successes), 1)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0][1], "out_of_stock")

        product.refresh_from_db()
        self.assertEqual(product.stock, 0)
        self.assertEqual(Order.objects.count(), 1)

    def test_bon_luong_cung_mua_san_pham_ton_kho_2_khong_bao_gio_am_kho(self):
        product = catalog_services.create_product(
            name="Zoro Enma Limited",
            category=self.category,
            series=self.series,
            brand=self.brand,
            price=Decimal(1800000),
            stock=2,
        )
        buyers = [
            self._create_buyer_with_cart(i, product, quantity=1)
            for i in range(1, 5)
        ]
        barrier = threading.Barrier(4)

        def worker(user, addr):
            try:
                barrier.wait(timeout=5)
                order = order_services.place_order(user, address_id=addr.pk)
                return ("ok", order.pk)
            except ValidationError as exc:
                return ("error", exc.code)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(worker, u, a) for u, a in buyers]
            results = [f.result() for f in futures]

        successes = [r for r in results if r[0] == "ok"]
        errors = [r for r in results if r[0] == "error"]

        self.assertEqual(len(successes), 2)
        self.assertEqual(len(errors), 2)
        for _, code in errors:
            self.assertEqual(code, "out_of_stock")

        product.refresh_from_db()
        self.assertEqual(product.stock, 0)
        self.assertEqual(Order.objects.count(), 2)

    def test_cung_mot_nguoi_gui_hai_request_dat_hang_dong_thoi_khong_tao_don_trung(self):
        product = catalog_services.create_product(
            name="Nami Figure",
            category=self.category,
            series=self.series,
            brand=self.brand,
            price=Decimal(1200000),
            stock=5,
        )
        user, addr = self._create_buyer_with_cart(10, product, quantity=2)
        barrier = threading.Barrier(2)

        def worker():
            try:
                barrier.wait(timeout=5)
                order = order_services.place_order(user, address_id=addr.pk)
                return ("ok", order.pk)
            except ValidationError as exc:
                return ("error", exc.code)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            f1 = pool.submit(worker)
            f2 = pool.submit(worker)
            results = [f1.result(), f2.result()]

        successes = [r for r in results if r[0] == "ok"]
        errors = [r for r in results if r[0] == "error"]

        self.assertEqual(len(successes), 1)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0][1], "empty_cart")

        product.refresh_from_db()
        self.assertEqual(product.stock, 3)
        self.assertEqual(Order.objects.filter(user=user).count(), 1)


class CartAndCheckoutIntegrationTests(TestCase):
    """Kiểm thử tích hợp toàn luồng: Giỏ hàng session -> Đăng nhập gộp giỏ -> Đặt hàng kèm Coupon -> Hủy đơn."""

    @classmethod
    def setUpTestData(cls):
        cls.category = catalog_services.create_category("Scale Figure")
        cls.series = catalog_services.create_series("One Piece")
        cls.brand = catalog_services.create_brand("Good Smile Company")
        cls.product = catalog_services.create_product(
            name="Sanji Raid Suit",
            category=cls.category,
            series=cls.series,
            brand=cls.brand,
            price=Decimal(1500000),
            stock=5,
        )
        cls.user = User.objects.create_user(
            email="flow@example.com",
            password="Password123!",
            full_name="Khách Luồng Chính",
            phone="0901234567",
        )
        cls.address = account_services.create_address(
            cls.user,
            receiver="Khách Luồng Chính",
            phone="0901234567",
            street="10 Nguyễn Huệ",
            ward="Phường Bến Nghé",
            district="Quận 1",
            province="TP. Hồ Chí Minh",
            is_default=True,
        )
        cls.coupon = Coupon.objects.create(
            code="FLOW100K",
            discount_type=Coupon.DiscountType.FIXED,
            discount_value=Decimal(100000),
            min_order_amount=Decimal(1000000),
            usage_limit=1,
        )

    def test_vong_doi_gio_hang_gop_gio_dat_hang_va_huy_don_hoan_kho(self):
        # 1. Khách chưa đăng nhập thêm 2 sản phẩm vào giỏ session
        resp_add = self.client.post(
            reverse("carts:add", args=[self.product.pk]),
            {"quantity": 2, "next": reverse("carts:cart")},
        )
        self.assertEqual(resp_add.status_code, 302)

        # 2. Khách đăng nhập -> giỏ session tự gộp vào giỏ DB
        resp_login = self.client.post(
            reverse("accounts:login"),
            {"email": "flow@example.com", "password": "Password123!"},
        )
        self.assertEqual(resp_login.status_code, 302)
        self.assertEqual(DbCartStore(self.user).quantities(), {self.product.pk: 2})

        # 3. Đặt hàng kèm mã giảm giá FLOW100K
        resp_checkout = self.client.post(
            reverse("orders:checkout"),
            {
                "address_id": str(self.address.pk),
                "payment_method": Order.PaymentMethod.COD,
                "coupon_code": "FLOW100K",
                "note": "Giao nhanh",
            },
        )
        order = Order.objects.get(user=self.user)
        self.assertRedirects(
            resp_checkout, reverse("orders:success", args=[order.pk])
        )
        self.assertEqual(order.subtotal, Decimal(3000000))
        self.assertEqual(order.discount_amount, Decimal(100000))
        self.assertEqual(order.shipping_fee, Decimal(30000))
        self.assertEqual(order.total, Decimal(2930000))

        self.product.refresh_from_db()
        self.coupon.refresh_from_db()
        self.assertEqual(self.product.stock, 3)
        self.assertEqual(self.coupon.used_count, 1)

        # 4. Khách hủy đơn -> hoàn lại tồn kho (5) và hoàn lại lượt dùng coupon (0)
        resp_cancel = self.client.post(reverse("orders:cancel", args=[order.pk]))
        self.assertRedirects(
            resp_cancel, reverse("orders:detail", args=[order.pk])
        )
        self.product.refresh_from_db()
        self.coupon.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(self.product.stock, 5)
        self.assertEqual(self.coupon.used_count, 0)


class CrossAppPermissionTests(TestCase):
    """Kiểm thử ma trận phân quyền trên các chức năng quan trọng (CN17, CN27)."""

    @classmethod
    def setUpTestData(cls):
        cls.category = catalog_services.create_category("Scale Figure")
        cls.series = catalog_services.create_series("One Piece")
        cls.brand = catalog_services.create_brand("Good Smile Company")
        cls.product = catalog_services.create_product(
            name="Chopper Figure",
            category=cls.category,
            series=cls.series,
            brand=cls.brand,
            price=Decimal(800000),
            stock=10,
        )
        cls.customer_a = User.objects.create_user(
            email="a@example.com",
            password="Password123!",
            full_name="Khách A",
        )
        cls.customer_b = User.objects.create_user(
            email="b@example.com",
            password="Password123!",
            full_name="Khách B",
        )
        cls.staff = User.objects.create_user(
            email="staff@example.com",
            password="Password123!",
            full_name="Nhân Viên",
            is_staff=True,
        )
        cls.admin = User.objects.create_superuser(
            email="admin@example.com",
            password="Password123!",
            full_name="Quản Trị Viên",
        )
        cls.addr_a = account_services.create_address(
            cls.customer_a,
            receiver="Khách A",
            phone="0901234567",
            street="1 Lê Lợi",
            ward="Phường 1",
            district="Quận 1",
            province="TP. Hồ Chí Minh",
            is_default=True,
        )
        cart_services.add_item(DbCartStore(cls.customer_a), cls.product.pk, 1)
        cls.order_a = order_services.place_order(
            cls.customer_a, address_id=cls.addr_a.pk
        )

    def test_khach_hang_b_khong_the_xem_huy_don_hoac_sua_dia_chi_cua_khach_a(self):
        client = Client()
        client.force_login(self.customer_b)

        # Xem chi tiết / trang thành công / hủy đơn của khách A -> 404
        self.assertEqual(
            client.get(reverse("orders:detail", args=[self.order_a.pk])).status_code,
            404,
        )
        self.assertEqual(
            client.get(reverse("orders:success", args=[self.order_a.pk])).status_code,
            404,
        )
        self.assertEqual(
            client.post(reverse("orders:cancel", args=[self.order_a.pk])).status_code,
            404,
        )
        # Sửa / xóa địa chỉ của khách A -> 404
        self.assertEqual(
            client.get(
                reverse("accounts:address_edit", args=[self.addr_a.pk])
            ).status_code,
            404,
        )
        self.assertEqual(
            client.post(
                reverse("accounts:address_delete", args=[self.addr_a.pk])
            ).status_code,
            404,
        )

    def test_ma_tran_quyen_truy_cap_dashboard_va_admin(self):
        dashboard_url = reverse("orders:dashboard")
        admin_orders_url = "/admin/orders/order/"
        admin_users_url = "/admin/accounts/user/"

        # 1. Khách ẩn danh -> 302 redirect trên cả 3 URL
        anon = Client()
        self.assertEqual(anon.get(dashboard_url).status_code, 302)
        self.assertEqual(anon.get(admin_orders_url).status_code, 302)
        self.assertEqual(anon.get(admin_users_url).status_code, 302)

        # 2. Khách hàng thường -> 403 trên dashboard, 302 trên /admin/
        cust = Client()
        cust.force_login(self.customer_a)
        self.assertEqual(cust.get(dashboard_url).status_code, 403)
        self.assertEqual(cust.get(admin_orders_url).status_code, 302)
        self.assertEqual(cust.get(admin_users_url).status_code, 302)

        # 3. Nhân viên -> 200 trên dashboard & admin orders, nhưng 403 trên admin users
        staff_client = Client()
        staff_client.force_login(self.staff)
        self.assertEqual(staff_client.get(dashboard_url).status_code, 200)
        self.assertEqual(staff_client.get(admin_orders_url).status_code, 200)
        self.assertEqual(staff_client.get(admin_users_url).status_code, 403)

        # 4. Admin -> 200 trên tất cả
        admin_client = Client()
        admin_client.force_login(self.admin)
        self.assertEqual(admin_client.get(dashboard_url).status_code, 200)
        self.assertEqual(admin_client.get(admin_orders_url).status_code, 200)
        self.assertEqual(admin_client.get(admin_users_url).status_code, 200)
