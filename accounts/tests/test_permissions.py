"""CN17: Kiểm thử phân quyền (khách / khách hàng / nhân viên / admin) và các trường hợp biên:
- Người thường truy cập URL admin hoặc view của nhân viên/admin.
- Nhân viên (is_staff=True) truy cập trang quản lý sản phẩm/đơn hàng được nhưng bị chặn ở quản lý User.
- Tài khoản bị khóa (is_active=False hoặc locked_until > now) khi vẫn còn session đang đăng nhập.
"""
from datetime import timedelta

from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from accounts.permissions import admin_required, staff_required
from catalog import services as catalog_services
from orders import services as order_services

PASS = "Mk-an-toan-123"


class RoleAndDecoratorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.customer = User.objects.create_user(
            "khach@example.com", PASS, full_name="Khách Hàng"
        )
        cls.staff = User.objects.create_user(
            "nhanvien@example.com", PASS, full_name="Nhân Viên", is_staff=True
        )
        cls.admin = User.objects.create_superuser(
            "admin@example.com", PASS, full_name="Quản Trị"
        )

    def test_thuoc_tinh_role_cua_user(self):
        self.assertEqual(self.customer.role, User.Role.CUSTOMER)
        self.assertEqual(self.staff.role, User.Role.STAFF)
        self.assertEqual(self.admin.role, User.Role.ADMIN)

    def test_decorator_staff_required_va_admin_required(self):
        factory = RequestFactory()

        @staff_required
        def staff_view(request):
            return HttpResponse("ok-staff")

        @admin_required
        def admin_view(request):
            return HttpResponse("ok-admin")

        # Khách hàng thường bị chặn 403 ở cả hai
        req = factory.get("/internal/")
        req.user = self.customer
        self.assertEqual(staff_view(req).status_code, 403)
        self.assertEqual(admin_view(req).status_code, 403)

        # Nhân viên vào được staff_view nhưng bị chặn 403 ở admin_view
        req.user = self.staff
        self.assertEqual(staff_view(req).status_code, 200)
        self.assertEqual(admin_view(req).status_code, 403)

        # Admin vào được cả hai
        req.user = self.admin
        self.assertEqual(staff_view(req).status_code, 200)
        self.assertEqual(admin_view(req).status_code, 200)


class AdminUrlPermissionBoundaryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.customer = User.objects.create_user(
            "khach@example.com", PASS, full_name="Khách Hàng"
        )
        cls.staff = User.objects.create_user(
            "nhanvien@example.com", PASS, full_name="Nhân Viên", is_staff=True
        )
        cls.admin = User.objects.create_superuser(
            "admin@example.com", PASS, full_name="Quản Trị"
        )
        cls.category = catalog_services.create_category("Scale Figure")
        cls.series = catalog_services.create_series("One Piece")
        cls.brand = catalog_services.create_brand("Good Smile Company")
        cls.product = catalog_services.create_product(
            name="Luffy",
            category=cls.category,
            series=cls.series,
            brand=cls.brand,
            price=1500000,
            stock=5,
        )

    def test_khach_chua_dang_nhap_truy_cap_admin_bi_chuyen_ve_login(self):
        for path in (
            "/admin/",
            "/admin/catalog/product/",
            "/admin/orders/order/",
            "/admin/accounts/user/",
        ):
            resp = self.client.get(path)
            self.assertEqual(resp.status_code, 302, path)
            self.assertIn("/admin/login/", resp["Location"])

    def test_nguoi_thuong_da_dang_nhap_truy_cap_url_admin_bi_chan(self):
        self.client.login(email=self.customer.email, password=PASS)
        for path in (
            "/admin/",
            "/admin/catalog/product/",
            f"/admin/catalog/product/{self.product.pk}/change/",
            "/admin/orders/order/",
            "/admin/accounts/user/",
        ):
            resp = self.client.get(path)
            # Django admin trả 302 về /admin/login/ hoặc 403 đối với tài khoản không phải staff
            self.assertIn(resp.status_code, (302, 403), path)
            if resp.status_code == 302:
                self.assertIn("/admin/login/", resp["Location"])

        # Cố POST xóa sản phẩm trong admin cũng bị chặn, sản phẩm vẫn còn nguyên
        post_resp = self.client.post(
            f"/admin/catalog/product/{self.product.pk}/delete/", {"post": "yes"}
        )
        self.assertIn(post_resp.status_code, (302, 403))
        self.assertTrue(
            catalog_services.Product.objects.filter(pk=self.product.pk).exists()
        )

    def test_nhan_vien_vao_duoc_san_pham_va_don_hang_nhung_bi_chan_o_quan_ly_user(self):
        self.client.login(email=self.staff.email, password=PASS)
        self.assertEqual(self.client.get("/admin/catalog/product/").status_code, 200)
        self.assertEqual(self.client.get("/admin/orders/order/").status_code, 200)

        # Nhân viên không được phép xem/thêm/sửa/xóa tài khoản User trong /admin/accounts/user/
        self.assertEqual(self.client.get("/admin/accounts/user/").status_code, 403)
        self.assertEqual(self.client.get("/admin/accounts/user/add/").status_code, 403)
        self.assertEqual(
            self.client.get(f"/admin/accounts/user/{self.customer.pk}/change/").status_code,
            403,
        )

    def test_admin_superuser_co_toan_quyen_quan_ly_user(self):
        self.client.login(email=self.admin.email, password=PASS)
        self.assertEqual(self.client.get("/admin/accounts/user/").status_code, 200)
        self.assertEqual(self.client.get("/admin/accounts/user/add/").status_code, 200)


class LockedAccountActiveSessionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = catalog_services.create_category("Scale Figure")
        cls.series = catalog_services.create_series("One Piece")
        cls.brand = catalog_services.create_brand("Good Smile Company")
        cls.product = catalog_services.create_product(
            name="Luffy",
            category=cls.category,
            series=cls.series,
            brand=cls.brand,
            price=1500000,
            stock=5,
        )

    def setUp(self):
        self.user = User.objects.create_user(
            "active@example.com", PASS, full_name="Người Dùng"
        )

    def test_tai_khoan_bi_khoa_is_active_false_khi_dang_con_session_bi_dang_xuat_ngay(self):
        self.client.login(email=self.user.email, password=PASS)
        self.assertIn("_auth_user_id", self.client.session)

        # Admin khóa tài khoản trong khi user vẫn đang giữ session đăng nhập
        User.objects.filter(pk=self.user.pk).update(is_active=False)

        resp = self.client.get(reverse("accounts:profile"), follow=True)
        self.assertRedirects(resp, reverse("accounts:login"))
        self.assertContains(resp, "Tài khoản của bạn đã bị khóa")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_tai_khoan_bi_khoa_tam_locked_until_khi_dang_con_session_bi_chan_va_dang_xuat(self):
        self.client.login(email=self.user.email, password=PASS)
        self.assertIn("_auth_user_id", self.client.session)

        # Tài khoản bị đặt locked_until trong tương lai khi vẫn còn session
        User.objects.filter(pk=self.user.pk).update(
            locked_until=timezone.now() + timedelta(minutes=15)
        )

        resp = self.client.post(
            reverse("accounts:profile"),
            {"full_name": "Tên Mới", "phone": "0901234567"},
            follow=True,
        )
        self.assertRedirects(resp, reverse("accounts:login"))
        self.assertContains(resp, "Tài khoản của bạn đã bị khóa")
        self.assertNotIn("_auth_user_id", self.client.session)

        self.user.refresh_from_db()
        self.assertEqual(self.user.full_name, "Người Dùng")

    def test_nhan_vien_bi_khoa_khi_dang_con_session_khong_thao_tac_duoc_admin(self):
        staff = User.objects.create_user(
            "staff_lock@example.com", PASS, full_name="Staff", is_staff=True
        )
        self.client.login(email=staff.email, password=PASS)
        self.assertEqual(self.client.get("/admin/orders/order/").status_code, 200)

        # Khóa tài khoản nhân viên giữa chừng
        User.objects.filter(pk=staff.pk).update(is_active=False)

        resp = self.client.get("/admin/orders/order/")
        self.assertEqual(resp.status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)
