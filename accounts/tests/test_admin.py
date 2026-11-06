from django.test import TestCase

from accounts.models import User

GOOD = "Mk-an-toan-123"


class UserAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("root@example.com", GOOD, full_name="Root")
        self.client.force_login(self.admin)

    def test_danh_sach_va_trang_sua(self):
        self.assertEqual(self.client.get("/admin/accounts/user/").status_code, 200)
        url = f"/admin/accounts/user/{self.admin.pk}/change/"
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_them_nguoi_dung_trong_admin(self):
        self.assertEqual(self.client.get("/admin/accounts/user/add/").status_code, 200)
        resp = self.client.post(
            "/admin/accounts/user/add/",
            {"email": "new@example.com", "full_name": "New", "password1": GOOD, "password2": GOOD},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(User.objects.get(email="new@example.com").check_password(GOOD))