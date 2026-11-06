import re

from django.contrib.staticfiles import finders
from django.test import override_settings

from catalog.tests.test_product_list import ListBase


def luminance(hex_color):
    r, g, b = (int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))

    def channel(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(a, b):
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def css_colors():
    path = finders.find("css/theme.css")
    with open(path, encoding="utf-8") as f:
        css = f.read()
    return dict(re.findall(r"--([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})\s*;", css))


class ThemeFileTests(ListBase):
    def test_trang_nap_tep_css(self):
        self.assertContains(self.client.get("/"), "/static/css/theme.css")
        self.assertIsNotNone(finders.find("css/theme.css"))

    def test_bang_mau_du_tuong_phan_chu_nen(self):
        c = css_colors()
        pairs = [
            ("text", "bg"), ("text", "surface"), ("text", "surface-2"),
            ("muted", "bg"), ("muted", "surface"), ("muted", "surface-2"),
            ("link", "bg"), ("link", "surface"),
            ("pink", "bg"), ("pink", "surface"),
        ]
        for fg, bg in pairs:
            self.assertGreaterEqual(contrast(c[fg], c[bg]), 4.5, f"{fg} trên {bg}")

    def test_chu_trang_tren_nut_gradient_du_tuong_phan(self):
        c = css_colors()
        for deep in ("purple-deep", "pink-deep"):
            self.assertGreaterEqual(contrast("#ffffff", c[deep]), 4.5, f"trắng trên {deep}")


class LayoutTests(ListBase):
    def test_menu_va_chan_trang_co_danh_muc_tren_trang_khac(self):
        self.make("Luffy")
        resp = self.client.get("/accounts/login/")
        self.assertContains(resp, 'href="/danh-muc/scale-figure/"', count=2)  # menu + chân trang

    def test_khong_co_danh_muc_thi_khong_co_menu_danh_muc(self):
        resp = self.client.get("/accounts/login/")
        self.assertNotContains(resp, 'class="menu"')
        self.assertContains(resp, "Đang cập nhật")

    @override_settings(PRODUCTS_PER_PAGE=2)
    def test_banner_chi_hien_o_trang_chu_trang_dau(self):
        for i in range(1, 6):
            self.make(f"Fig {i}")
        self.assertContains(self.client.get("/"), 'class="hero"')
        self.assertNotContains(self.client.get("/", {"page": 2}), 'class="hero"')
        self.assertNotContains(self.client.get("/danh-muc/scale-figure/"), 'class="hero"')

    def test_ten_nguoi_dung_chua_html_van_bi_escape_o_dau_trang(self):
        from accounts.models import User

        user = User.objects.create_user("x@example.com", "Mk-an-toan-123", full_name="<i>a</i>")
        self.client.force_login(user)
        resp = self.client.get("/")
        self.assertContains(resp, "&lt;i&gt;a&lt;/i&gt;")
        self.assertNotContains(resp, "<i>a</i>")