from django.test import Client

from carts import services
from carts.models import CartItem
from carts.stores import DbCartStore
from carts.tests.base import PASSWORD, CartTestBase


class ViewBase(CartTestBase):
    def setUp(self):
        self.product = self.make_product(stock=5)

    def add(self, quantity=1, product=None, **extra):
        product = product or self.product
        data = {"quantity": quantity, **extra}
        return self.client.post(f"/gio-hang/them/{product.pk}/", data)

    def session_cart(self):
        return self.client.session.get("cart", {})

    def login(self, user=None):
        self.client.login(email=(user or self.user).email, password=PASSWORD)


class GuestAddTests(ViewBase):
    def test_them_vao_gio_luu_trong_session_va_chuyen_den_trang_gio(self):
        resp = self.add(2)
        self.assertRedirects(resp, "/gio-hang/")
        self.assertEqual(self.session_cart(), {str(self.product.pk): 2})
        self.assertEqual(CartItem.objects.count(), 0)

    def test_thong_bao_da_them(self):
        resp = self.add(1, follow=False)
        resp = self.client.get("/gio-hang/")
        self.assertContains(resp, "Đã thêm")

    def test_khong_gui_so_luong_thi_mac_dinh_la_1(self):
        self.client.post(f"/gio-hang/them/{self.product.pk}/")
        self.assertEqual(self.session_cart(), {str(self.product.pk): 1})

    def test_chi_nhan_post(self):
        resp = self.client.get(f"/gio-hang/them/{self.product.pk}/")
        self.assertEqual(resp.status_code, 405)
        self.assertEqual(self.session_cart(), {})

    def test_bat_buoc_csrf(self):
        client = Client(enforce_csrf_checks=True)
        resp = client.post(f"/gio-hang/them/{self.product.pk}/", {"quantity": 1})
        self.assertEqual(resp.status_code, 403)

    def test_san_pham_khong_ton_tai_hoac_dang_an_tra_404(self):
        hidden = self.make_product("An", is_active=False)
        self.assertEqual(self.add(1, product=hidden).status_code, 404)
        self.assertEqual(self.client.post("/gio-hang/them/999999/", {"quantity": 1}).status_code, 404)
        self.assertEqual(self.session_cart(), {})

    def test_so_luong_khong_hop_le_bao_loi_va_khong_them(self):
        for bad in ("abc", "0", "-1", "", "1.5", "1e2"):
            resp = self.add(bad, next="/")
            self.assertEqual(resp.status_code, 302, bad)
        resp = self.client.get("/gio-hang/")
        self.assertContains(resp, "Số lượng phải là số nguyên từ 1 trở lên")
        self.assertEqual(self.session_cart(), {})

    def test_vuot_ton_kho_bao_loi_va_giu_nguyen(self):
        self.add(3)
        self.add(3)
        self.assertEqual(self.session_cart(), {str(self.product.pk): 3})
        self.assertContains(self.client.get("/gio-hang/"), "Chỉ còn 5 sản phẩm")

    def test_het_hang(self):
        empty = self.make_product("Het", stock=0)
        self.add(1, product=empty)
        self.assertContains(self.client.get("/gio-hang/"), "đã hết hàng")
        self.assertEqual(self.session_cart(), {})

    def test_next_an_toan_duoc_dung_de_quay_lai(self):
        resp = self.add(1, next=f"/san-pham/{self.product.slug}/")
        self.assertRedirects(resp, f"/san-pham/{self.product.slug}/")

    def test_next_ra_ngoai_trang_web_bi_bo_qua(self):
        for evil in ("https://evil.example/", "//evil.example/", "javascript:alert(1)"):
            resp = self.add(1, next=evil)
            self.assertRedirects(resp, "/gio-hang/", msg_prefix=evil)

    def test_loi_van_chuyen_ve_next_khi_next_hop_le(self):
        resp = self.add("abc", next="/")
        self.assertRedirects(resp, "/")


class GuestUpdateRemoveTests(ViewBase):
    def setUp(self):
        super().setUp()
        self.add(2)

    def update(self, quantity, product=None):
        product = product or self.product
        return self.client.post(f"/gio-hang/sua/{product.pk}/", {"quantity": quantity})

    def test_sua_so_luong(self):
        self.assertRedirects(self.update(4), "/gio-hang/")
        self.assertEqual(self.session_cart(), {str(self.product.pk): 4})

    def test_sua_so_luong_khong_hop_le_giu_nguyen(self):
        for bad in ("0", "-2", "abc", ""):
            self.update(bad)
        self.assertEqual(self.session_cart(), {str(self.product.pk): 2})
        self.assertContains(self.client.get("/gio-hang/"), "Số lượng phải là số nguyên từ 1 trở lên")

    def test_sua_vuot_ton_kho_giu_nguyen(self):
        self.update(9)
        self.assertEqual(self.session_cart(), {str(self.product.pk): 2})
        self.assertContains(self.client.get("/gio-hang/"), "Chỉ còn 5 sản phẩm")

    def test_sua_san_pham_khong_co_trong_gio(self):
        other = self.make_product("Zoro")
        self.update(1, product=other)
        self.assertEqual(self.session_cart(), {str(self.product.pk): 2})
        self.assertContains(self.client.get("/gio-hang/"), "không có trong giỏ")

    def test_sua_chi_nhan_post(self):
        self.assertEqual(self.client.get(f"/gio-hang/sua/{self.product.pk}/").status_code, 405)

    def test_xoa(self):
        resp = self.client.post(f"/gio-hang/xoa/{self.product.pk}/")
        self.assertRedirects(resp, "/gio-hang/")
        self.assertEqual(self.session_cart(), {})

    def test_xoa_chi_nhan_post(self):
        self.assertEqual(self.client.get(f"/gio-hang/xoa/{self.product.pk}/").status_code, 405)
        self.assertEqual(self.session_cart(), {str(self.product.pk): 2})

    def test_xoa_san_pham_khong_co_trong_gio_khong_gay_loi(self):
        self.assertEqual(self.client.post("/gio-hang/xoa/999999/").status_code, 302)
        self.assertEqual(self.session_cart(), {str(self.product.pk): 2})

    def test_xoa_san_pham_da_bi_an_van_xoa_duoc(self):
        self.product.is_active = False
        self.product.save()
        self.client.post(f"/gio-hang/xoa/{self.product.pk}/")
        self.assertEqual(self.session_cart(), {})


class CartPageTests(ViewBase):
    def test_gio_trong(self):
        resp = self.client.get("/gio-hang/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Giỏ hàng của bạn đang trống")

    def test_hien_dong_hang_va_tong_tien(self):
        zoro = self.make_product("Zoro", price=1000000)
        self.add(2)
        self.add(1, product=zoro)
        resp = self.client.get("/gio-hang/")
        self.assertContains(resp, "Luffy")
        self.assertContains(resp, "Zoro")
        self.assertContains(resp, "3.000.000 ₫")  # 2 x 1.500.000
        self.assertContains(resp, "4.000.000 ₫")  # tổng

    def test_ten_san_pham_chua_html_bi_escape(self):
        evil = self.make_product("<script>alert(1)</script>")
        self.add(1, product=evil)
        resp = self.client.get("/gio-hang/")
        self.assertNotContains(resp, "<script>alert(1)</script>")
        self.assertContains(resp, "&lt;script&gt;alert(1)&lt;/script&gt;")

    def test_dong_het_hang_hoac_bi_an_co_canh_bao_va_khong_tinh_tien(self):
        hidden = self.make_product("An", price=1000000)
        self.add(1)
        self.add(1, product=hidden)
        hidden.is_active = False
        hidden.save()
        resp = self.client.get("/gio-hang/")
        self.assertContains(resp, "không còn được bán")
        self.assertContains(resp, "1.500.000 ₫")
        self.assertNotContains(resp, "2.500.000 ₫")

    def test_ton_kho_giam_thi_canh_bao(self):
        self.add(4)
        self.product.stock = 2
        self.product.save()
        self.assertContains(self.client.get("/gio-hang/"), "Chỉ còn 2")

    def test_so_luong_tren_header(self):
        self.add(3)
        self.assertContains(self.client.get("/"), 'data-cart-count="3"')

    def test_header_khong_hien_so_khi_gio_trong(self):
        self.assertNotContains(self.client.get("/"), "data-cart-count")


class PriceChangeViewTests(ViewBase):
    def test_nguoi_dung_dang_nhap_thay_canh_bao_doi_gia(self):
        self.login()
        self.add(1)
        self.product.price = 1800000
        self.product.save()
        resp = self.client.get("/gio-hang/")
        self.assertContains(resp, "Giá đã thay đổi")
        self.assertContains(resp, "1.500.000 ₫")
        self.assertContains(resp, "1.800.000 ₫")

    def test_khach_khong_co_canh_bao_nhung_van_dung_gia_moi(self):
        self.add(1)
        self.product.price = 1800000
        self.product.save()
        resp = self.client.get("/gio-hang/")
        self.assertNotContains(resp, "Giá đã thay đổi")
        self.assertContains(resp, "1.800.000 ₫")


class LoggedInTests(ViewBase):
    def test_gio_luu_trong_database_khong_luu_session(self):
        self.login()
        self.add(2)
        self.assertEqual(DbCartStore(self.user).quantities(), {self.product.pk: 2})
        self.assertEqual(self.session_cart(), {})

    def test_sua_va_xoa(self):
        self.login()
        self.add(2)
        self.client.post(f"/gio-hang/sua/{self.product.pk}/", {"quantity": 4})
        self.assertEqual(DbCartStore(self.user).quantities(), {self.product.pk: 4})
        self.client.post(f"/gio-hang/xoa/{self.product.pk}/")
        self.assertEqual(DbCartStore(self.user).quantities(), {})

    def test_gio_cua_hai_nguoi_dung_tach_biet(self):
        self.login()
        self.add(2)
        other = Client()
        other.login(email=self.other_user.email, password=PASSWORD)
        resp = other.get("/gio-hang/")
        self.assertContains(resp, "Giỏ hàng của bạn đang trống")
        self.assertEqual(DbCartStore(self.other_user).quantities(), {})

    def test_giu_gio_sau_khi_dang_xuat_dang_nhap_lai(self):
        self.login()
        self.add(2)
        self.client.post("/accounts/logout/")
        self.assertContains(self.client.get("/gio-hang/"), "Giỏ hàng của bạn đang trống")
        self.login()
        self.assertContains(self.client.get("/gio-hang/"), "Luffy")

    def test_so_luong_tren_header(self):
        self.login()
        self.add(3)
        self.assertContains(self.client.get("/"), 'data-cart-count="3"')


class ProductDetailButtonTests(ViewBase):
    def test_trang_chi_tiet_co_form_them_vao_gio(self):
        resp = self.client.get(f"/san-pham/{self.product.slug}/")
        self.assertContains(resp, f'action="/gio-hang/them/{self.product.pk}/"')
        self.assertContains(resp, "Thêm vào giỏ")
        self.assertContains(resp, 'max="5"')
        self.assertContains(resp, f'name="next" value="/san-pham/{self.product.slug}/"')
        self.assertContains(resp, "csrfmiddlewaretoken")

    def test_het_hang_thi_khong_co_form_them(self):
        empty = self.make_product("Het", stock=0)
        resp = self.client.get(f"/san-pham/{empty.slug}/")
        self.assertNotContains(resp, "Thêm vào giỏ")
        self.assertNotContains(resp, f"/gio-hang/them/{empty.pk}/")
