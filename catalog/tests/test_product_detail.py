from django.db import connection
from django.test.utils import CaptureQueriesContext

from catalog import selectors, services
from catalog.tests.test_product_list import ListBase, make_image


class DetailPageTests(ListBase):
    def test_hien_day_du_thong_tin(self):
        p = self.make(
            "Luffy Gear 5", scale="1/7", material="PVC", height_cm=25,
            description="Dòng một\nDòng hai",
        )
        resp = self.client.get(f"/san-pham/{p.slug}/")
        self.assertEqual(resp.status_code, 200)
        for text in (
            "Luffy Gear 5", "1.500.000 ₫", "One Piece", "Good Smile Company",
            "1/7", "PVC", "25 cm", "Dòng một", "Dòng hai", "Scale Figure",
        ):
            self.assertContains(resp, text)
        self.assertContains(resp, '<title>Luffy Gear 5</title>', html=True)

    def test_khong_hien_dong_thong_so_neu_de_trong(self):
        p = self.make("Luffy")
        resp = self.client.get(f"/san-pham/{p.slug}/")
        for label in ("Tỉ lệ", "Chất liệu", "Chiều cao", "Mô tả"):
            self.assertNotContains(resp, label)

    def test_mo_ta_chua_html_bi_escape(self):
        p = self.make("Luffy", description="<script>alert(1)</script>")
        resp = self.client.get(f"/san-pham/{p.slug}/")
        self.assertContains(resp, "&lt;script&gt;alert(1)&lt;/script&gt;")
        self.assertNotContains(resp, "<script>alert(1)</script>")

    def test_ten_chua_html_bi_escape(self):
        p = self.make("<b>x</b> Luffy")
        resp = self.client.get(f"/san-pham/{p.slug}/")
        self.assertNotContains(resp, "<b>x</b> Luffy")
        self.assertContains(resp, "&lt;b&gt;x&lt;/b&gt; Luffy")

    def test_duong_dan_breadcrumb_ve_danh_muc(self):
        p = self.make("Luffy")
        resp = self.client.get(f"/san-pham/{p.slug}/")
        self.assertContains(resp, '<a href="/danh-muc/scale-figure/">Scale Figure</a> ›')
        self.assertContains(resp, "<span>Luffy</span>")


class NotFoundTests(ListBase):
    def test_san_pham_bi_an_tra_ve_404(self):
        p = self.make("Luffy", is_active=False)
        self.assertEqual(self.client.get(f"/san-pham/{p.slug}/").status_code, 404)

    def test_san_pham_da_xoa_tra_ve_404(self):
        p = self.make("Luffy")
        url = f"/san-pham/{p.slug}/"
        self.assertEqual(self.client.get(url).status_code, 200)
        p.delete()
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_slug_sai_tra_ve_404(self):
        self.make("Luffy")
        for bad in ("khong-co", "luffy-", "LUFFY", "Luffy", "a b", "luffy%00", "../admin"):
            self.assertEqual(self.client.get(f"/san-pham/{bad}/").status_code, 404, bad)

    def test_selector_tra_ve_none_cho_an_va_sai_hoa_thuong(self):
        self.make("Luffy")
        self.make("Zoro", is_active=False)
        self.assertIsNotNone(selectors.get_active_product_by_slug("luffy"))
        self.assertIsNone(selectors.get_active_product_by_slug("zoro"))
        self.assertIsNone(selectors.get_active_product_by_slug("LUFFY"))


class StockTests(ListBase):
    def test_con_hang(self):
        p = self.make("Luffy", stock=3)
        resp = self.client.get(f"/san-pham/{p.slug}/")
        self.assertContains(resp, "Còn hàng (3)")
        self.assertNotContains(resp, "Hết hàng")

    def test_het_hang_van_xem_duoc(self):
        p = self.make("Luffy", stock=0)
        resp = self.client.get(f"/san-pham/{p.slug}/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Hết hàng", count=1)
        self.assertNotContains(resp, "Còn hàng")


class GalleryTests(ListBase):
    def test_nhieu_anh_co_anh_lon_va_hang_thu_nho(self):
        p = self.make("Luffy")
        for i in range(3):
            services.add_product_image(p, make_image(f"{i}.png"))
        resp = self.client.get(f"/san-pham/{p.slug}/")
        self.assertContains(resp, 'id="main-image"')
        self.assertContains(resp, "data-src=", count=3)

    def test_mot_anh_khong_co_hang_thu_nho(self):
        p = self.make("Luffy")
        services.add_product_image(p, make_image())
        resp = self.client.get(f"/san-pham/{p.slug}/")
        self.assertContains(resp, 'id="main-image"')
        self.assertNotContains(resp, "data-src=")

    def test_anh_chinh_hien_dau_tien(self):
        p = self.make("Luffy")
        services.add_product_image(p, make_image("a.png"))
        main = services.add_product_image(p, make_image("b.png"), is_main=True)
        resp = self.client.get(f"/san-pham/{p.slug}/")
        self.assertEqual(resp.context["images"][0], main)

    def test_khong_co_anh_dung_anh_du_phong(self):
        p = self.make("Luffy")
        resp = self.client.get(f"/san-pham/{p.slug}/")
        self.assertContains(resp, "/static/img/no-image.svg")
        self.assertNotContains(resp, 'id="main-image"')

    def test_anh_loi_404_co_du_phong(self):
        p = self.make("Luffy")
        services.add_product_image(p, make_image())
        self.assertContains(self.client.get(f"/san-pham/{p.slug}/"), "onerror=")


class RelatedTests(ListBase):
    def test_cung_bo_anime_len_truoc_roi_cung_danh_muc(self):
        other_series = services.create_series("Naruto")
        main = self.make("Chinh")
        same_category = services.create_product(
            name="Cung danh muc", category=self.category, series=other_series,
            brand=self.brand, price=1000, stock=1,
        )
        same_series = services.create_product(
            name="Cung bo", category=self.other_category, series=self.series,
            brand=self.brand, price=1000, stock=1,
        )
        related = list(selectors.list_related_products(main))
        self.assertEqual(related, [same_series, same_category])

    def test_loai_chinh_no_hang_an_va_san_pham_khong_lien_quan(self):
        other_series = services.create_series("Naruto")
        main = self.make("Chinh")
        self.make("An", is_active=False)
        services.create_product(
            name="Khong lien quan", category=self.other_category, series=other_series,
            brand=self.brand, price=1000,
        )
        self.assertEqual(list(selectors.list_related_products(main)), [])

    def test_toi_da_4_san_pham(self):
        main = self.make("Chinh")
        for i in range(7):
            self.make(f"Lien quan {i}")
        self.assertEqual(len(selectors.list_related_products(main)), 4)

    def test_trang_hien_khoi_lien_quan_va_the_bam_duoc(self):
        main = self.make("Chinh")
        rel = self.make("Lien quan")
        resp = self.client.get(f"/san-pham/{main.slug}/")
        self.assertContains(resp, "Sản phẩm liên quan")
        self.assertContains(resp, f'href="/san-pham/{rel.slug}/"')

    def test_khong_co_lien_quan_thi_khong_hien_khoi(self):
        p = self.make("Chinh")
        self.assertNotContains(self.client.get(f"/san-pham/{p.slug}/"), "Sản phẩm liên quan")


class ListLinksTests(ListBase):
    def test_the_o_danh_sach_bam_duoc_vao_trang_chi_tiet(self):
        p = self.make("Luffy")
        self.assertContains(self.client.get("/"), f'href="/san-pham/{p.slug}/"')


class QueryCountTests(ListBase):
    def test_so_truy_van_khong_tang_theo_so_anh_va_san_pham_lien_quan(self):
        main = self.make("Chinh")
        services.add_product_image(main, make_image("m.png"))
        services.add_product_image(self.make("Lien quan 0"), make_image("r0.png"))
        url = f"/san-pham/{main.slug}/"
        with CaptureQueriesContext(connection) as few:
            self.client.get(url)
        for i in range(3):
            services.add_product_image(main, make_image(f"x{i}.png"))
        for i in range(1, 4):
            services.add_product_image(self.make(f"Lien quan {i}"), make_image(f"r{i}.png"))
        with CaptureQueriesContext(connection) as many:
            self.client.get(url)
        self.assertEqual(len(few), len(many))
        # sản phẩm, ảnh sản phẩm, liên quan, ảnh liên quan, danh mục ở menu
        self.assertEqual(len(many), 5)