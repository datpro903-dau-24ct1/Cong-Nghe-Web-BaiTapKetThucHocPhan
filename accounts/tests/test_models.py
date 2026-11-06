from django.test import TestCase

from accounts.models import User


class UserModelTests(TestCase):
    def test_create_user_chuan_hoa_email_va_bam_mat_khau(self):
        u = User.objects.create_user("  Alice@Example.COM ", "Mk-an-toan-123", full_name="Alice")
        self.assertEqual(u.email, "alice@example.com")
        self.assertNotEqual(u.password, "Mk-an-toan-123")
        self.assertTrue(u.check_password("Mk-an-toan-123"))
        self.assertTrue(u.is_active)
        self.assertFalse(u.is_staff)
        self.assertFalse(u.is_superuser)

    def test_thieu_email_bao_loi(self):
        with self.assertRaises(ValueError):
            User.objects.create_user("   ", "Mk-an-toan-123", full_name="A")

    def test_create_superuser(self):
        u = User.objects.create_superuser("root@example.com", "Mk-an-toan-123", full_name="Root")
        self.assertTrue(u.is_staff and u.is_superuser)

    def test_superuser_khong_duoc_tat_is_staff(self):
        with self.assertRaises(ValueError):
            User.objects.create_superuser(
                "r@example.com", "Mk-an-toan-123", full_name="R", is_staff=False
            )