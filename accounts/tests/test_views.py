from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts import services
from accounts.models import User

GOOD = "Mk-an-toan-123"


class RegisterViewTests(TestCase):
    url = "/accounts/register/"

    def post(self, **kw):
        data = dict(
            email="alice@example.com", full_name="Alice", password=GOOD, password_confirm=GOOD
        )
        data.update(kw)
        return self.client.post(self.url, data)

    def test_trang_dang_ky_hien_thi(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_dang_ky_thanh_cong_tu_dang_nhap_va_ve_trang_chu(self):
        resp = self.post()
        self.assertRedirects(resp, reverse("home"))
        self.assertIn("_auth_user_id", self.client.session)
        self.assertTrue(User.objects.filter(email="alice@example.com").exists())

    def test_email_trung_hien_loi_tren_trang(self):
        services.register_user(email="alice@example.com", password=GOOD, full_name="A")
        resp = self.post()
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Email này đã được đăng ký.")
        self.assertEqual(User.objects.count(), 1)

    def test_mat_khau_yeu_hien_loi(self):
        resp = self.post(password="12345678", password_confirm="12345678")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(User.objects.count(), 0)
        self.assertTrue(resp.context["form"].errors["password"])

    def test_hai_mat_khau_khong_khop(self):
        resp = self.post(password_confirm="khac-hoan-toan-1")
        self.assertContains(resp, "Hai mật khẩu không khớp.")
        self.assertEqual(User.objects.count(), 0)

    def test_da_dang_nhap_thi_chuyen_ve_trang_chu(self):
        self.post()
        self.assertRedirects(self.client.get(self.url), reverse("home"))

    def test_ho_ten_chua_html_bi_escape(self):
        self.post(full_name="<b>x</b>")
        resp = self.client.get(reverse("home"))
        self.assertContains(resp, "&lt;b&gt;x&lt;/b&gt;")
        self.assertNotContains(resp, "<b>x</b>")


class LoginViewTests(TestCase):
    url = "/accounts/login/"

    def setUp(self):
        User.objects.create_user("bob@example.com", GOOD, full_name="Bob")

    def post(self, password=GOOD, **extra):
        data = {"email": "bob@example.com", "password": password}
        data.update(extra)
        return self.client.post(self.url, data)

    def test_dang_nhap_thanh_cong_ve_trang_chu(self):
        self.assertRedirects(self.post(), reverse("home"))
        self.assertIn("_auth_user_id", self.client.session)

    def test_sai_mat_khau_hien_loi_chung(self):
        resp = self.post(password="sai-mat-khau")
        self.assertContains(resp, "Email hoặc mật khẩu không đúng.")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_chuyen_ve_trang_next_noi_bo(self):
        resp = self.post(next="/admin/")
        self.assertRedirects(resp, "/admin/", fetch_redirect_response=False)

    def test_next_ra_ngoai_bi_bo_qua(self):
        for bad in ("https://evil.example.com/", "//evil.example.com/", "javascript:alert(1)"):
            self.client.logout()
            resp = self.post(next=bad)
            self.assertRedirects(resp, reverse("home"), msg_prefix=bad)

    def test_trang_dang_nhap_giu_gia_tri_next(self):
        resp = self.client.get(self.url, {"next": "/admin/"})
        self.assertContains(resp, 'name="next" value="/admin/"')

    def test_khoa_tam_hien_thong_bao_thu_lai_sau(self):
        for _ in range(services.MAX_FAILED_LOGINS):
            self.post(password="sai-mat-khau")
        resp = self.post()
        self.assertContains(resp, "thử lại sau")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_da_dang_nhap_thi_khong_vao_lai_trang_dang_nhap(self):
        self.post()
        self.assertRedirects(self.client.get(self.url), reverse("home"))


class LogoutViewTests(TestCase):
    def setUp(self):
        User.objects.create_user("bob@example.com", GOOD, full_name="Bob")
        self.client.login(email="bob@example.com", password=GOOD)

    def test_dang_xuat_bang_post(self):
        resp = self.client.post("/accounts/logout/")
        self.assertRedirects(resp, reverse("home"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_get_khong_duoc_dang_xuat(self):
        self.assertEqual(self.client.get("/accounts/logout/").status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)