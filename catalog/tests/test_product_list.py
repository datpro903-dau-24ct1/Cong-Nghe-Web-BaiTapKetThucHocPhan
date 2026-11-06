import io
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from PIL import Image

from catalog import services


def make_image(name="a.png"):
    buf = io.BytesIO()
    Image.new("RGB", (2, 2), "red").save(buf, "PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


class ListBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = services.create_category("Scale Figure")
        cls.other_category = services.create_category("Nendoroid")
        cls.series = services.create_series("One Piece")
        cls.brand = services.create_brand("Good Smile Company")

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        override = override_settings(MEDIA_ROOT=tmp.name)
        override.enable()
        self.addCleanup(override.disable)

    def make(self, name, category=None, **kw):
        data = dict(
            category=category or self.category, series=self.series,
            brand=self.brand, price=1500000, stock=3,
        )
        data.update(kw)
        return services.create_product(name=name, **data)


class HomePageTests(ListBase):
    def test_chua_co_san_pham(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Chưa có sản phẩm nào")

    def test_chi_hien_san_pham_dang_ban(self):
        self.make("Luffy")
        self.make("Zoro", is_active=False)
        resp = self.client.get("/")
        self.assertContains(resp, "Luffy")
        self.assertNotContains(resp, "Zoro")

    def test_hien_gia_series_va_hang(self):
        self.make("Luffy")
        resp = self.client.get("/")
        self.assertContains(resp, "1.500.000 ₫")
        self.assertContains(resp, "One Piece")
        self.assertContains(resp, "Good Smile Company")

    def test_nhan_het_hang_chi_hien_o_san_pham_het_hang(self):
        self.make("Con hang", stock=3)
        self.make("Het hang", stock=0)
        self.assertContains(self.client.get("/"), "Hết hàng", count=1)

    def test_ten_san_pham_chua_html_bi_escape(self):
        self.make("<b>x</b> Luffy")
        resp = self.client.get("/")
        self.assertContains(resp, "&lt;b&gt;x&lt;/b&gt; Luffy")
        self.assertNotContains(resp, "<b>x</b> Luffy")


@override_settings(PRODUCTS_PER_PAGE=5)
class PaginationTests(ListBase):
    def setUp(self):
        super().setUp()
        for i in range(1, 13):
            self.make(f"SP {i:02d}")

    def test_trang_dau_hien_5_san_pham_moi_nhat(self):
        resp = self.client.get("/")
        for n in (12, 11, 10, 9, 8):
            self.assertContains(resp, f"SP {n:02d}")
        self.assertNotContains(resp, "SP 07")
        self.assertContains(resp, "Trang 1 / 3")

    def test_trang_cuoi_chi_con_2_san_pham(self):
        resp = self.client.get("/", {"page": 3})
        self.assertContains(resp, "SP 02")
        self.assertContains(resp, "SP 01")
        self.assertNotContains(resp, "SP 03")
        self.assertNotContains(resp, "Sau ›")

    def test_trang_vuot_qua_so_trang_ve_trang_cuoi(self):
        for value in ("99", "999999999999999999999"):
            resp = self.client.get("/", {"page": value})
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.context["page_obj"].number, 3)

    def test_trang_khong_hop_le_ve_trang_dau(self):
        for value in ("0", "-5", "abc", "", "1.5"):
            resp = self.client.get("/", {"page": value})
            self.assertEqual(resp.status_code, 200, value)
            self.assertEqual(resp.context["page_obj"].number, 1, value)

    def test_chi_mot_trang_thi_khong_hien_dieu_huong(self):
        with override_settings(PRODUCTS_PER_PAGE=50):
            self.assertNotContains(self.client.get("/"), "Trang 1 /")


class ImageTests(ListBase):
    def test_san_pham_co_anh_dung_duong_dan_media(self):
        p = self.make("Luffy")
        services.add_product_image(p, make_image())
        self.assertContains(self.client.get("/"), "/media/products/")

    def test_san_pham_khong_co_anh_dung_anh_du_phong(self):
        self.make("Luffy")
        self.assertContains(self.client.get("/"), "/static/img/no-image.svg")

    def test_anh_loi_404_van_co_du_phong_onerror(self):
        p = self.make("Luffy")
        services.add_product_image(p, make_image())
        self.assertContains(self.client.get("/"), "onerror=")

    def test_so_truy_van_khong_tang_theo_so_san_pham(self):
        for i in range(2):
            services.add_product_image(self.make(f"A{i}"), make_image(f"a{i}.png"))
        with CaptureQueriesContext(connection) as few:
            self.client.get("/")
        for i in range(8):
            services.add_product_image(self.make(f"B{i}"), make_image(f"b{i}.png"))
        with CaptureQueriesContext(connection) as many:
            self.client.get("/")
        self.assertEqual(len(few), len(many))


class CategoryPageTests(ListBase):
    def test_chi_hien_san_pham_cua_danh_muc(self):
        self.make("Luffy")
        self.make("Mikasa Nendo", category=self.other_category)
        resp = self.client.get("/danh-muc/scale-figure/")
        self.assertContains(resp, "Luffy")
        self.assertNotContains(resp, "Mikasa Nendo")

    def test_danh_muc_rong_van_mo_duoc(self):
        resp = self.client.get("/danh-muc/nendoroid/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Chưa có sản phẩm nào trong danh mục này")

    def test_danh_muc_khong_ton_tai_tra_ve_404(self):
        self.assertEqual(self.client.get("/danh-muc/khong-co/").status_code, 404)

    def test_menu_chi_hien_danh_muc_co_san_pham_dang_ban(self):
        self.make("Luffy")
        self.make("An", category=self.other_category, is_active=False)
        resp = self.client.get("/")
        self.assertContains(resp, "/danh-muc/scale-figure/")
        self.assertNotContains(resp, "/danh-muc/nendoroid/")

    @override_settings(PRODUCTS_PER_PAGE=2)
    def test_phan_trang_trong_danh_muc(self):
        for i in range(1, 6):
            self.make(f"Fig {i}")
        resp = self.client.get("/danh-muc/scale-figure/", {"page": 3})
        self.assertEqual(resp.context["page_obj"].number, 3)
        self.assertContains(resp, "Fig 1")