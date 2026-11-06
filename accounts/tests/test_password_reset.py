from datetime import timedelta

from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from accounts import services
from accounts.models import User


class PasswordResetServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            email="member@example.com",
            password="OldPassword123!",
            full_name="Thành Viên",
        )
        cls.inactive_user = User.objects.create_user(
            email="inactive@example.com",
            password="OldPassword123!",
            full_name="Bị Khóa",
            is_active=False,
        )

    def _make_uid_and_token(self, user=None):
        user = user or self.user
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        return uidb64, token

    def test_yeu_cau_dat_lai_mat_khau_cho_email_ton_tai_gui_mail(self):
        sent = []

        def fake_send_mail(subject, message, from_email, recipient_list):
            sent.append((subject, message, from_email, recipient_list))

        ok = services.request_password_reset(
            "  MEMBER@example.com ",
            reset_url_builder=lambda uid, tok: f"https://shop.test/reset/{uid}/{tok}/",
            send_mail_fn=fake_send_mail,
        )
        self.assertTrue(ok)
        self.assertEqual(len(sent), 1)
        subject, body, _, recipients = sent[0]
        self.assertEqual(recipients, ["member@example.com"])
        self.assertIn("https://shop.test/reset/", body)

    def test_email_khong_ton_tai_hoac_bi_khoa_khong_gui_mail_va_khong_bao_loi(self):
        sent = []
        for email in ("ghost@example.com", "inactive@example.com", "not-an-email", ""):
            ok = services.request_password_reset(
                email,
                reset_url_builder=lambda uid, tok: f"https://shop.test/reset/{uid}/{tok}/",
                send_mail_fn=lambda *a, **kw: sent.append(a),
            )
            self.assertFalse(ok)
        self.assertEqual(len(sent), 0)

    def test_dat_lai_mat_khau_thanh_cong_va_xoa_khoa_dang_nhap_tam_thoi(self):
        self.user.failed_login_count = 4
        self.user.locked_until = timezone.now() + timedelta(minutes=15)
        self.user.save(update_fields=["failed_login_count", "locked_until"])

        uidb64, token = self._make_uid_and_token()
        services.reset_password_with_token(
            uidb64, token, new_password="NewStrongPassword123!"
        )

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewStrongPassword123!"))
        self.assertEqual(self.user.failed_login_count, 0)
        self.assertIsNone(self.user.locked_until)

    def test_chan_dung_lai_token_sau_khi_da_doi_mat_khau(self):
        uidb64, token = self._make_uid_and_token()
        services.reset_password_with_token(
            uidb64, token, new_password="NewStrongPassword123!"
        )

        with self.assertRaises(ValidationError) as ctx:
            services.verify_password_reset_token(uidb64, token)
        self.assertEqual(ctx.exception.code, "invalid_token")

        with self.assertRaises(ValidationError) as ctx2:
            services.reset_password_with_token(
                uidb64, token, new_password="AnotherPassword123!"
            )
        self.assertEqual(ctx2.exception.code, "invalid_token")

    @override_settings(PASSWORD_RESET_TIMEOUT=-1)
    def test_chan_token_het_han(self):
        uidb64, token = self._make_uid_and_token()
        with self.assertRaises(ValidationError) as ctx:
            services.verify_password_reset_token(uidb64, token)
        self.assertEqual(ctx.exception.code, "invalid_token")

        with self.assertRaises(ValidationError) as ctx2:
            services.reset_password_with_token(
                uidb64, token, new_password="NewStrongPassword123!"
            )
        self.assertEqual(ctx2.exception.code, "invalid_token")

    def test_chan_uid_hoac_token_sai_dinh_dang(self):
        uidb64, _ = self._make_uid_and_token()
        for bad_uid, bad_token in (
            ("!!!not-base64!!!", "any-token"),
            (urlsafe_base64_encode(force_bytes(99999999)), "any-token"),
            (uidb64, "wrong-token"),
            ("", ""),
        ):
            with self.assertRaises(ValidationError) as ctx:
                services.verify_password_reset_token(bad_uid, bad_token)
            self.assertEqual(ctx.exception.code, "invalid_token")

    def test_mat_khau_moi_yeu_bao_loi_va_khong_lam_hong_token(self):
        uidb64, token = self._make_uid_and_token()
        with self.assertRaises(ValidationError) as ctx:
            services.reset_password_with_token(uidb64, token, new_password="123")
        self.assertIn("new_password", ctx.exception.message_dict)

        # Token vẫn còn hiệu lực để người dùng nhập lại mật khẩu đủ mạnh
        services.reset_password_with_token(
            uidb64, token, new_password="ValidStrongPassword123!"
        )
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("ValidStrongPassword123!"))

    def test_doi_mat_khau_khi_da_dang_nhap(self):
        with self.assertRaises(ValidationError) as ctx:
            services.change_password(
                self.user,
                old_password="WrongOldPassword!",
                new_password="NewStrongPassword123!",
            )
        self.assertIn("old_password", ctx.exception.message_dict)

        services.change_password(
            self.user,
            old_password="OldPassword123!",
            new_password="ChangedPassword123!",
        )
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("ChangedPassword123!"))


class PasswordResetViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            email="user@example.com",
            password="OldPassword123!",
            full_name="Người Dùng",
        )

    def test_quen_mat_khau_khong_tiet_lo_email_ton_tai_hay_khong(self):
        url = reverse("accounts:password_reset")
        expected_msg = (
            "Nếu email tồn tại trong hệ thống, liên kết đặt lại mật khẩu đã được gửi."
        )

        # 1. Email không tồn tại
        resp_missing = self.client.post(
            url, {"email": "nobody@example.com"}, follow=True
        )
        self.assertEqual(resp_missing.status_code, 200)
        self.assertContains(resp_missing, expected_msg)
        self.assertEqual(len(mail.outbox), 0)

        # 2. Email tồn tại -> cùng thông báo cho người dùng, nhưng có gửi 1 email
        resp_existing = self.client.post(
            url, {"email": "user@example.com"}, follow=True
        )
        self.assertEqual(resp_existing.status_code, 200)
        self.assertContains(resp_existing, expected_msg)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["user@example.com"])

    def test_luong_dat_lai_mat_khau_qua_link_email_va_chan_dung_lai_link(self):
        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        confirm_url = reverse("accounts:password_reset_confirm", args=[uidb64, token])

        # Mở form đặt lại mật khẩu
        resp_get = self.client.get(confirm_url)
        self.assertEqual(resp_get.status_code, 200)
        self.assertContains(resp_get, "Đặt lại mật khẩu")

        # Gửi hai mật khẩu không khớp
        resp_mismatch = self.client.post(
            confirm_url,
            {
                "new_password": "BrandNewPassword123!",
                "new_password_confirm": "DifferentPassword123!",
            },
        )
        self.assertEqual(resp_mismatch.status_code, 200)
        self.assertContains(resp_mismatch, "Hai mật khẩu không khớp")

        # Đặt lại mật khẩu thành công
        resp_ok = self.client.post(
            confirm_url,
            {
                "new_password": "BrandNewPassword123!",
                "new_password_confirm": "BrandNewPassword123!",
            },
            follow=True,
        )
        self.assertEqual(resp_ok.status_code, 200)
        self.assertContains(resp_ok, "Đặt lại mật khẩu thành công")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("BrandNewPassword123!"))

        # Dùng lại cùng link token -> bị từ chối và chuyển về trang yêu cầu mới
        resp_reuse = self.client.get(confirm_url, follow=True)
        self.assertEqual(resp_reuse.status_code, 200)
        self.assertContains(
            resp_reuse, "Liên kết đặt lại mật khẩu không hợp lệ hoặc đã hết hạn."
        )

    @override_settings(PASSWORD_RESET_TIMEOUT=-1)
    def test_link_het_han_chuyen_huong_kem_thong_bao_loi(self):
        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        confirm_url = reverse("accounts:password_reset_confirm", args=[uidb64, token])

        resp = self.client.get(confirm_url, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(
            resp, "Liên kết đặt lại mật khẩu không hợp lệ hoặc đã hết hạn."
        )

    def test_doi_mat_khau_tren_web_giu_nguyen_phien_dang_nhap(self):
        change_url = reverse("accounts:password_change")
        # Chưa đăng nhập -> redirect tới login
        self.assertEqual(self.client.get(change_url).status_code, 302)

        self.client.force_login(self.user)
        resp = self.client.post(
            change_url,
            {
                "old_password": "OldPassword123!",
                "new_password": "UpdatedPassword123!",
                "new_password_confirm": "UpdatedPassword123!",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Đã đổi mật khẩu thành công.")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("UpdatedPassword123!"))
        # Vẫn đang đăng nhập (không bị văng về login khi vào profile)
        self.assertEqual(self.client.get(reverse("accounts:profile")).status_code, 200)
