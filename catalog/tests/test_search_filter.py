"""CN08: tìm kiếm, lọc (series, hãng, khoảng giá, tỉ lệ) và sắp xếp danh sách sản phẩm."""
from django.db import connection
from django.test import override_settings
from django.test.utils import CaptureQueriesContext

from catalog import services
from catalog.tests.test_product_list import ListBase

KHONG_KET_QUA = "Không tìm thấy sản phẩm phù hợp"


def names_in_order(resp):
    return [p.name for p in resp.context["page_obj"].object_list]


class SearchBase(ListBase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.naruto = services.create_series("Naruto")
        cls.gsc = cls.brand
        cls.bandai = services.create_brand("Bandai")

    def make(self, name, **kw):
        return super().make(name, **kw)


class KeywordSearchTests(SearchBase):
    def setUp(self):
        super().setUp()
        self.make("Luffy Gear 5")
        self.make("Zoro Wano")

    def test_tim_theo_tu_khoa_khong_phan_biet_hoa_thuong(self):
        resp = self.client.get("/", {"q": "lUfFy"})
        self.assertEqual(names_in_order(resp), ["Luffy Gear 5"])

    def test_tu_khoa_la_mot_phan_cua_ten(self):
        resp = self.client.get("/", {"q": "wan"})
        self.assertEqual(names_in_order(resp), ["Zoro Wano"])

    def test_tu_khoa_rong_hoac_chi_khoang_trang_la_khong_loc(self):
        for value in ("", "   "):
            resp = self.client.get("/", {"q": value})
            self.assertEqual(len(names_in_order(resp)), 2, repr(value))

    def test_khong_co_ket_qua_hien_thong_bao_rieng(self):
        resp = self.client.get("/", {"q": "khong-co-san-pham-nay"})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, KHONG_KET_QUA)
        self.assertNotContains(resp, "Chưa có sản phẩm nào")

    def test_chua_co_san_pham_nao_van_hien_thong_bao_cu(self):
        from catalog.models import Product
        Product.objects.all().delete()
        resp = self.client.get("/")
        self.assertContains(resp, "Chưa có sản phẩm nào")
        self.assertNotContains(resp, KHONG_KET_QUA)

    def test_khong_tim_thay_san_pham_dang_an(self):
        self.make("Luffy An", is_active=False)
        resp = self.client.get("/", {"q": "Luffy"})
        self.assertEqual(names_in_order(resp), ["Luffy Gear 5"])

    def test_tim_trong_danh_muc_chi_tra_ve_san_pham_cua_danh_muc(self):
        self.make("Luffy Nendo", category=self.other_category)
        resp = self.client.get(f"/danh-muc/{self.other_category.slug}/", {"q": "Luffy"})
        self.assertEqual(names_in_order(resp), ["Luffy Nendo"])


class AccentTests(SearchBase):
    """Có dấu / không dấu: dựa vào collation utf8mb4_unicode_ci của MariaDB (phương án B)."""

    def setUp(self):
        super().setUp()
        self.make("Hoàng Tử Bé")
        self.make("Rem Re:Zero")

    def test_go_khong_dau_van_tim_ra_ten_co_dau(self):
        resp = self.client.get("/", {"q": "hoang tu"})
        self.assertEqual(names_in_order(resp), ["Hoàng Tử Bé"])

    def test_go_co_dau_van_tim_ra_ten_khong_dau(self):
        self.make("Hoang Gia")
        resp = self.client.get("/", {"q": "Hoàng"})
        self.assertEqual(set(names_in_order(resp)), {"Hoàng Tử Bé", "Hoang Gia"})

    def test_ten_tieng_nhat(self):
        self.make("ルフィ ギア5")
        resp = self.client.get("/", {"q": "ルフィ"})
        self.assertEqual(names_in_order(resp), ["ルフィ ギア5"])


class SpecialCharacterTests(SearchBase):
    def setUp(self):
        super().setUp()
        self.make("Luffy")
        self.make("100% Zoro")
        self.make("Nami_Orange")

    def test_phan_tram_va_gach_duoi_khong_phai_ky_tu_dai_dien(self):
        self.assertEqual(names_in_order(self.client.get("/", {"q": "%"})), ["100% Zoro"])
        self.assertEqual(names_in_order(self.client.get("/", {"q": "_"})), ["Nami_Orange"])

    def test_dau_nhay_va_gach_cheo_khong_gay_loi(self):
        for value in ("'", '"', "\\", "'; DROP TABLE catalog_product; --", "a" * 500):
            resp = self.client.get("/", {"q": value})
            self.assertEqual(resp.status_code, 200, value[:20])

    def test_tu_khoa_html_bi_escape_khi_hien_lai(self):
        resp = self.client.get("/", {"q": "<script>alert(1)</script>"})
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "<script>alert(1)</script>")

    def test_tu_khoa_qua_dai_bao_loi_khong_loc(self):
        resp = self.client.get("/", {"q": "a" * 500})
        self.assertEqual(len(names_in_order(resp)), 3)
        self.assertTrue(resp.context["filter_form"].errors)


class SeriesBrandFilterTests(SearchBase):
    def setUp(self):
        super().setUp()
        self.make("Luffy")  # One Piece / Good Smile Company
        self.make("Naruto Uzumaki", series=self.naruto, brand=self.bandai)
        self.make("Sasuke", series=self.naruto)

    def test_loc_theo_series(self):
        resp = self.client.get("/", {"series": self.naruto.slug})
        self.assertEqual(set(names_in_order(resp)), {"Naruto Uzumaki", "Sasuke"})

    def test_loc_theo_hang(self):
        resp = self.client.get("/", {"brand": self.bandai.slug})
        self.assertEqual(names_in_order(resp), ["Naruto Uzumaki"])

    def test_loc_ket_hop_series_va_hang(self):
        resp = self.client.get("/", {"series": self.naruto.slug, "brand": self.gsc.slug})
        self.assertEqual(names_in_order(resp), ["Sasuke"])

    def test_series_hoac_hang_khong_ton_tai_bao_loi_va_khong_loc(self):
        for params in ({"series": "khong-co"}, {"brand": "khong-co"}):
            resp = self.client.get("/", params)
            self.assertEqual(resp.status_code, 200)
            self.assertTrue(resp.context["filter_form"].errors, params)
            self.assertEqual(len(names_in_order(resp)), 3, params)
            self.assertContains(resp, 'class="error"')


class PriceFilterTests(SearchBase):
    def setUp(self):
        super().setUp()
        self.make("Re", price=500000)
        self.make("Trung", price=1000000)
        self.make("Dat", price=2000000)

    def test_chi_gia_toi_thieu(self):
        resp = self.client.get("/", {"price_min": 1000000})
        self.assertEqual(set(names_in_order(resp)), {"Trung", "Dat"})

    def test_chi_gia_toi_da(self):
        resp = self.client.get("/", {"price_max": 1000000})
        self.assertEqual(set(names_in_order(resp)), {"Re", "Trung"})

    def test_khoang_gia_bao_gom_hai_dau_mut(self):
        resp = self.client.get("/", {"price_min": 500000, "price_max": 1000000})
        self.assertEqual(set(names_in_order(resp)), {"Re", "Trung"})

    def test_min_bang_max(self):
        resp = self.client.get("/", {"price_min": 1000000, "price_max": 1000000})
        self.assertEqual(names_in_order(resp), ["Trung"])

    def test_min_lon_hon_max_bao_loi_va_khong_loc_theo_gia(self):
        resp = self.client.get("/", {"price_min": 2000000, "price_max": 500000})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Giá tối thiểu không được lớn hơn giá tối đa")
        self.assertEqual(len(names_in_order(resp)), 3)

    def test_gia_khong_hop_le_bao_loi_va_khong_gay_500(self):
        for value in ("abc", "-1", "1.5", "1e3", "99999999999999999999"):
            for key in ("price_min", "price_max"):
                resp = self.client.get("/", {key: value})
                self.assertEqual(resp.status_code, 200, (key, value))
                self.assertTrue(resp.context["filter_form"].errors, (key, value))
                self.assertEqual(len(names_in_order(resp)), 3, (key, value))

    def test_khong_co_san_pham_trong_khoang_gia(self):
        resp = self.client.get("/", {"price_min": 5000000})
        self.assertContains(resp, KHONG_KET_QUA)


class ScaleFilterTests(SearchBase):
    def setUp(self):
        super().setUp()
        self.make("A", scale="1/7")
        self.make("B", scale="1/8")
        self.make("C", scale="1/7")
        self.make("D")  # không có tỉ lệ
        self.make("E", scale="1/12", is_active=False)

    def test_loc_theo_ti_le(self):
        resp = self.client.get("/", {"scale": "1/7"})
        self.assertEqual(set(names_in_order(resp)), {"A", "C"})

    def test_ti_le_khong_co_san_pham_dang_ban_la_khong_hop_le(self):
        resp = self.client.get("/", {"scale": "1/12"})
        self.assertTrue(resp.context["filter_form"].errors)
        self.assertEqual(len(names_in_order(resp)), 4)

    def test_ti_le_la_chuoi_la_khong_gay_500(self):
        for value in ("abc", "%", "1/7' OR 1=1"):
            resp = self.client.get("/", {"scale": value})
            self.assertEqual(resp.status_code, 200, value)
            self.assertTrue(resp.context["filter_form"].errors, value)

    def test_form_chi_liet_ke_ti_le_dang_ban(self):
        resp = self.client.get("/")
        self.assertEqual(
            [value for value, _ in resp.context["filter_form"].fields["scale"].choices if value],
            ["1/7", "1/8"],
        )


class SortTests(SearchBase):
    def setUp(self):
        super().setUp()
        self.make("B", price=2000000)
        self.make("A", price=3000000)
        self.make("C", price=1000000)  # mới nhất

    def test_mac_dinh_la_moi_nhat(self):
        self.assertEqual(names_in_order(self.client.get("/")), ["C", "A", "B"])

    def test_gia_tang_dan(self):
        resp = self.client.get("/", {"sort": "price_asc"})
        self.assertEqual(names_in_order(resp), ["C", "B", "A"])

    def test_gia_giam_dan(self):
        resp = self.client.get("/", {"sort": "price_desc"})
        self.assertEqual(names_in_order(resp), ["A", "B", "C"])

    def test_ten_a_den_z(self):
        resp = self.client.get("/", {"sort": "name_asc"})
        self.assertEqual(names_in_order(resp), ["A", "B", "C"])

    def test_sort_moi_nhat_tuong_minh(self):
        resp = self.client.get("/", {"sort": "newest"})
        self.assertEqual(names_in_order(resp), ["C", "A", "B"])

    def test_sort_khong_hop_le_bao_loi_va_giu_thu_tu_mac_dinh(self):
        for value in ("abc", "price", "-price", "id; DROP"):
            resp = self.client.get("/", {"sort": value})
            self.assertEqual(resp.status_code, 200, value)
            self.assertTrue(resp.context["filter_form"].errors, value)
            self.assertEqual(names_in_order(resp), ["C", "A", "B"], value)

    def test_cung_gia_thi_thu_tu_on_dinh(self):
        self.make("D", price=1000000)
        first = names_in_order(self.client.get("/", {"sort": "price_asc"}))
        second = names_in_order(self.client.get("/", {"sort": "price_asc"}))
        self.assertEqual(first, second)
        self.assertEqual(first[:2], ["D", "C"])  # cùng giá: mới hơn lên trước


class CombinedAndPaginationTests(SearchBase):
    def test_ket_hop_tat_ca_bo_loc(self):
        self.make("Luffy A", price=1000000, scale="1/7")
        self.make("Luffy B", price=2000000, scale="1/7")
        self.make("Luffy C", price=3000000, scale="1/7")
        self.make("Luffy D", price=2000000, scale="1/8")
        self.make("Zoro", price=2000000, scale="1/7")
        resp = self.client.get("/", {
            "q": "luffy", "series": self.series.slug, "brand": self.gsc.slug,
            "price_min": 1500000, "price_max": 3000000, "scale": "1/7", "sort": "price_desc",
        })
        self.assertEqual(names_in_order(resp), ["Luffy C", "Luffy B"])

    @override_settings(PRODUCTS_PER_PAGE=5)
    def test_phan_trang_giu_nguyen_bo_loc(self):
        for i in range(1, 13):
            self.make(f"Luffy {i:02d}")
        self.make("Zoro")
        resp = self.client.get("/", {"q": "luffy", "sort": "name_asc"})
        self.assertContains(resp, "Trang 1 / 3")
        self.assertContains(resp, "page=2")
        self.assertContains(resp, "q=luffy")
        self.assertContains(resp, "sort=name_asc")
        resp = self.client.get("/", {"q": "luffy", "sort": "name_asc", "page": 3})
        self.assertEqual(names_in_order(resp), ["Luffy 11", "Luffy 12"])

    @override_settings(PRODUCTS_PER_PAGE=5)
    def test_phan_trang_khong_lap_tham_so_page_cu(self):
        for i in range(1, 13):
            self.make(f"Luffy {i:02d}")
        resp = self.client.get("/", {"q": "luffy", "page": 2})
        self.assertNotContains(resp, "page=2&amp;page=")
        self.assertNotContains(resp, "page=2&page=")

    def test_giu_gia_tri_da_chon_trong_form(self):
        self.make("Luffy", scale="1/7")
        resp = self.client.get("/", {
            "q": "Luffy", "series": self.series.slug, "price_min": 100, "scale": "1/7",
        })
        self.assertContains(resp, 'value="Luffy"')
        self.assertContains(resp, 'value="100"')
        self.assertContains(resp, f'<option value="{self.series.slug}" selected>')
        self.assertContains(resp, '<option value="1/7" selected>')

    def test_so_truy_van_khong_tang_theo_so_san_pham(self):
        for i in range(2):
            self.make(f"Luffy {i}")
        params = {"q": "luffy", "series": self.series.slug, "sort": "price_asc"}
        self.client.get("/", params)  # làm nóng cache (content type, session...)
        with CaptureQueriesContext(connection) as few:
            self.client.get("/", params)
        for i in range(2, 8):
            self.make(f"Luffy {i}")
        with CaptureQueriesContext(connection) as many:
            self.client.get("/", params)
        self.assertEqual(len(few), len(many))
