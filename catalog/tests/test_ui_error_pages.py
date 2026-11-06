"""CN26: Kiểm thử giao diện responsive, trang lỗi 404/500/403, messages, lazy image & tắt JS."""
from pathlib import Path

from django.conf import settings
from django.test import RequestFactory, TestCase
from django.urls import reverse

from accounts.models import User
from animeshop import views as error_views
from catalog import services
from catalog.tests.test_product_list import ListBase, make_image


class ErrorPagesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.customer = User.objects.create_user(
            email="customer@example.com",
            password="Password123!",
            full_name="Khách Thường",
        )

    def test_trang_404_tuy_chinh_hien_thi_tieng_viet_va_nut_ve_trang_chu(self):
        resp = self.client.get("/duong-dan-khong-ton-tai-404/")
        self.assertEqual(resp.status_code, 404)
        self.assertContains(resp, "404", status_code=404)
        self.assertContains(resp, "Không tìm thấy trang", status_code=404)
        self.assertContains(resp, 'href="/"', status_code=404)

    def test_trang_500_tuy_chinh_khong_phu_thuoc_db_va_tra_ve_500(self):
        rf = RequestFactory()
        request = rf.get("/loi-500/")
        resp = error_views.error_500_view(request)
        self.assertEqual(resp.status_code, 500)
        content = resp.content.decode("utf-8")
        self.assertIn("500", content)
        self.assertIn("Đã xảy ra lỗi hệ thống", content)
        self.assertIn('href="/"', content)

    def test_trang_403_tuy_chinh_khi_khong_du_quyen(self):
        self.client.force_login(self.customer)
        resp = self.client.get(reverse("orders:dashboard"))
        self.assertEqual(resp.status_code, 403)
        self.assertContains(resp, "403", status_code=403)
        self.assertContains(resp, "Không có quyền truy cập", status_code=403)


class ResponsiveAndProgressiveEnhancementTests(ListBase):
    def test_messages_hien_thi_voi_aria_live_va_class_trang_thai(self):
        p = self.make("Luffy Figure", stock=5)
        resp = self.client.post(
            reverse("carts:add", args=[p.pk]),
            {"quantity": 1, "next": "/"},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'class="messages"')
        self.assertContains(resp, 'aria-live="polite"')
        self.assertContains(resp, "success")

    def test_anh_san_pham_co_lazy_loading_async_decoding_va_fallback_khi_tat_js(self):
        p = self.make("Luffy Gear 5", stock=5)
        services.add_product_image(p, make_image("1.png"), is_main=True)
        services.add_product_image(p, make_image("2.png"))

        # Trang chủ: thẻ ảnh có loading="lazy", decoding="async" và data-fallback
        home_resp = self.client.get("/")
        self.assertContains(home_resp, 'loading="lazy"')
        self.assertContains(home_resp, 'decoding="async"')
        self.assertContains(home_resp, "data-fallback=")

        # Trang chi tiết: có cả nút thumbnail (khi bật JS) và khối <noscript> (khi tắt JS)
        detail_resp = self.client.get(reverse("product_detail", args=[p.slug]))
        self.assertContains(detail_resp, "data-src=", count=2)
        self.assertContains(detail_resp, "<noscript>")

    def test_file_css_co_media_queries_cho_man_hinh_nho_va_trang_loi(self):
        css_path = Path(settings.BASE_DIR) / "static" / "css" / "theme.css"
        css_text = css_path.read_text(encoding="utf-8")
        self.assertIn("@media (max-width: 768px)", css_text)
        self.assertIn("@media (max-width: 480px)", css_text)
        self.assertIn(".error-page", css_text)
        self.assertIn(".messages li.success", css_text)
        self.assertIn(".messages li.warning", css_text)
