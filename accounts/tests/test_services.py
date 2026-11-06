from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from accounts import services
from accounts.models import User

GOOD = "Mk-an-toan-123"


def codes(exc, field):
    return [e.code for e in exc.error_dict[field]]


class RegisterTests(TestCase):
    def register(self, **kw):
        data = dict(email="alice@example.com", password=GOOD, full_name="Alice")
        data.update(kw)
        return services.register_user(**data)

    def test_dang_ky_thanh_cong(self):
        u = self.register(email="  Alice@Example.com ")
        self.assertEqual(u.email, "alice@example.com")
        self.assertTrue(u.check_password(GOOD))

    def test_email_trung_ke_ca_khac_hoa_thuong(self):
        self.register()
        with self.assertRaises(ValidationError) as cm:
            self.register(email="ALICE@example.com")
        self.assertEqual(codes(cm.exception, "email"), ["duplicate_email"])
        self.assertEqual(User.objects.count(), 1)

    def test_email_sai_dinh_dang(self):
        for bad in ("", "abc", "a@", "@b.com"):
            with self.assertRaises(ValidationError) as cm:
                self.register(email=bad)
            self.assertEqual(codes(cm.exception, "email"), ["invalid_email"])

    def test_mat_khau_yeu(self):
        cases = {
            "ngan": "password_too_short",
            "qwertyuiop": "password_too_common",
            "58392016473": "password_entirely_numeric",
            "alice@example.com": "password_too_similar",
        }
        for pw, code in cases.items():
            with self.assertRaises(ValidationError) as cm:
                self.register(password=pw)
            self.assertIn(code, codes(cm.exception, "password"), pw)
        self.assertEqual(User.objects.count(), 0)

    def test_mat_khau_rong_hoac_none(self):
        for bad in ("", None):
            with self.assertRaises(ValidationError) as cm:
                self.register(password=bad)
            self.assertIn("password", cm.exception.error_dict)

    def test_ho_ten_trong_hoac_qua_dai(self):
        for bad, code in (("   ", "blank_full_name"), ("x" * 151, "full_name_too_long")):
            with self.assertRaises(ValidationError) as cm:
                self.register(full_name=bad)
            self.assertEqual(codes(cm.exception, "full_name"), [code])

    def test_nhieu_loi_cung_luc(self):
        with self.assertRaises(ValidationError) as cm:
            self.register(email="abc", password="ngan", full_name="")
        self.assertEqual(set(cm.exception.error_dict), {"email", "password", "full_name"})


class AuthenticateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("bob@example.com", GOOD, full_name="Bob")

    def fail(self, email="bob@example.com", password="sai-mat-khau"):
        with self.assertRaises(ValidationError) as cm:
            services.authenticate_user(email, password)
        return cm.exception.code

    def test_dang_nhap_dung(self):
        self.assertEqual(services.authenticate_user("bob@example.com", GOOD), self.user)

    def test_email_khong_phan_biet_hoa_thuong_va_khoang_trang(self):
        self.assertEqual(services.authenticate_user("  BOB@Example.com ", GOOD), self.user)

    def test_sai_mat_khau_va_email_khong_ton_tai_cung_mot_thong_bao(self):
        self.assertEqual(self.fail(), "invalid_credentials")
        self.assertEqual(self.fail(email="khong-co@example.com"), "invalid_credentials")

    def test_email_khong_ton_tai_khong_tao_ban_ghi(self):
        self.fail(email="khong-co@example.com")
        self.assertEqual(User.objects.count(), 1)

    def test_khoa_sau_5_lan_sai_ke_ca_khi_nhap_dung(self):
        for _ in range(services.MAX_FAILED_LOGINS):
            self.assertEqual(self.fail(), "invalid_credentials")
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.locked_until)
        self.assertEqual(self.fail(password=GOOD), "locked")

    def test_het_han_khoa_thi_dang_nhap_lai_duoc_va_xoa_bo_dem(self):
        User.objects.filter(pk=self.user.pk).update(
            failed_login_count=0, locked_until=timezone.now() - timedelta(minutes=1)
        )
        services.authenticate_user("bob@example.com", GOOD)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.locked_until)
        self.assertEqual(self.user.failed_login_count, 0)

    def test_dang_nhap_dung_reset_bo_dem_sai(self):
        for _ in range(3):
            self.fail()
        services.authenticate_user("bob@example.com", GOOD)
        self.user.refresh_from_db()
        self.assertEqual(self.user.failed_login_count, 0)

    def test_tai_khoan_bi_vo_hieu_khong_dang_nhap_duoc(self):
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        self.assertEqual(self.fail(password=GOOD), "invalid_credentials")