"""Services/selectors giỏ hàng: chạy cùng một bộ test cho cả giỏ session lẫn giỏ database."""
from django.core.exceptions import ValidationError
from django.db import connection
from django.test.utils import CaptureQueriesContext

from carts import selectors, services
from carts.models import CartItem
from carts.stores import DbCartStore, SessionCartStore
from carts.tests.base import CartTestBase


class StoreContract:
    """Hành vi chung của mọi loại giỏ; lớp con chỉ cần cung cấp make_store()."""

    def make_store(self):
        raise NotImplementedError

    def setUp(self):
        self.store = self.make_store()
        self.product = self.make_product(stock=5)

    def assertError(self, code, func, *args, **kwargs):
        with self.assertRaises(ValidationError) as ctx:
            func(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)

    # ---- thêm
    def test_them_san_pham_moi(self):
        services.add_item(self.store, self.product.pk, 2)
        self.assertEqual(self.store.quantities(), {self.product.pk: 2})

    def test_them_lai_thi_cong_don(self):
        services.add_item(self.store, self.product.pk, 2)
        services.add_item(self.store, self.product.pk, 1)
        self.assertEqual(self.store.quantities(), {self.product.pk: 3})

    def test_them_dung_bang_ton_kho_thi_duoc(self):
        services.add_item(self.store, self.product.pk, 5)
        self.assertEqual(self.store.quantities()[self.product.pk], 5)

    def test_them_vuot_ton_kho_bi_tu_choi_va_giu_nguyen(self):
        services.add_item(self.store, self.product.pk, 2)
        self.assertError("exceeds_stock", services.add_item, self.store, self.product.pk, 4)
        self.assertEqual(self.store.quantities(), {self.product.pk: 2})

    def test_them_vuot_ton_kho_khi_chua_co_trong_gio(self):
        self.assertError("exceeds_stock", services.add_item, self.store, self.product.pk, 6)
        self.assertEqual(self.store.quantities(), {})

    def test_thong_bao_vuot_ton_kho_neu_so_con_lai(self):
        with self.assertRaises(ValidationError) as ctx:
            services.add_item(self.store, self.product.pk, 6)
        self.assertIn("5", ctx.exception.messages[0])

    def test_het_hang(self):
        empty = self.make_product("Het hang", stock=0)
        self.assertError("out_of_stock", services.add_item, self.store, empty.pk, 1)

    def test_san_pham_dang_an_hoac_khong_ton_tai(self):
        hidden = self.make_product("An", is_active=False)
        self.assertError("product_unavailable", services.add_item, self.store, hidden.pk, 1)
        self.assertError("product_unavailable", services.add_item, self.store, 999999, 1)
        self.assertEqual(self.store.quantities(), {})

    def test_so_luong_khong_hop_le(self):
        for bad in (0, -1, None, "abc", "", 1.5, True):
            self.assertError("invalid_quantity", services.add_item, self.store, self.product.pk, bad)
        self.assertEqual(self.store.quantities(), {})

    def test_so_luong_la_chuoi_so_van_duoc_chap_nhan(self):
        services.add_item(self.store, self.product.pk, "2")
        self.assertEqual(self.store.quantities(), {self.product.pk: 2})

    # ---- sửa số lượng
    def test_sua_so_luong(self):
        services.add_item(self.store, self.product.pk, 1)
        services.set_quantity(self.store, self.product.pk, 4)
        self.assertEqual(self.store.quantities(), {self.product.pk: 4})

    def test_sua_giam_so_luong(self):
        services.add_item(self.store, self.product.pk, 4)
        services.set_quantity(self.store, self.product.pk, 1)
        self.assertEqual(self.store.quantities(), {self.product.pk: 1})

    def test_sua_so_luong_khong_hop_le_giu_nguyen(self):
        services.add_item(self.store, self.product.pk, 2)
        for bad in (0, -3, "x", None):
            self.assertError("invalid_quantity", services.set_quantity, self.store, self.product.pk, bad)
        self.assertEqual(self.store.quantities(), {self.product.pk: 2})

    def test_sua_vuot_ton_kho_giu_nguyen(self):
        services.add_item(self.store, self.product.pk, 2)
        self.assertError("exceeds_stock", services.set_quantity, self.store, self.product.pk, 6)
        self.assertEqual(self.store.quantities(), {self.product.pk: 2})

    def test_sua_san_pham_khong_co_trong_gio(self):
        self.assertError("not_in_cart", services.set_quantity, self.store, self.product.pk, 1)

    def test_sua_san_pham_da_bi_an(self):
        services.add_item(self.store, self.product.pk, 2)
        self.product.is_active = False
        self.product.save()
        self.assertError("product_unavailable", services.set_quantity, self.store, self.product.pk, 1)

    # ---- xóa
    def test_xoa_san_pham(self):
        other = self.make_product("Zoro")
        services.add_item(self.store, self.product.pk, 1)
        services.add_item(self.store, other.pk, 1)
        services.remove_item(self.store, self.product.pk)
        self.assertEqual(self.store.quantities(), {other.pk: 1})

    def test_xoa_san_pham_khong_co_trong_gio_khong_gay_loi(self):
        services.remove_item(self.store, self.product.pk)
        services.remove_item(self.store, 999999)
        self.assertEqual(self.store.quantities(), {})

    def test_xoa_duoc_ca_san_pham_da_bi_an(self):
        services.add_item(self.store, self.product.pk, 1)
        self.product.is_active = False
        self.product.save()
        services.remove_item(self.store, self.product.pk)
        self.assertEqual(self.store.quantities(), {})

    # ---- đọc giỏ
    def test_dong_hang_va_tong_tien(self):
        zoro = self.make_product("Zoro", price=1000000, stock=9)
        services.add_item(self.store, self.product.pk, 2)  # 2 x 1.500.000
        services.add_item(self.store, zoro.pk, 3)          # 3 x 1.000.000
        lines = selectors.get_cart_lines(self.store)
        self.assertEqual([l.product.name for l in lines], ["Luffy", "Zoro"])
        self.assertEqual([l.line_total for l in lines], [3000000, 3000000])
        self.assertEqual(selectors.get_cart_total(lines), 6000000)
        self.assertEqual(selectors.count_items(self.store), 5)

    def test_gio_trong(self):
        self.assertEqual(selectors.get_cart_lines(self.store), [])
        self.assertEqual(selectors.get_cart_total([]), 0)
        self.assertEqual(selectors.count_items(self.store), 0)

    def test_dong_hang_het_hang_hoac_bi_an_khong_tinh_vao_tong(self):
        hidden = self.make_product("An", price=1000000, stock=5)
        sold_out = self.make_product("Het", price=1000000, stock=5)
        services.add_item(self.store, self.product.pk, 1)
        services.add_item(self.store, hidden.pk, 1)
        services.add_item(self.store, sold_out.pk, 1)
        hidden.is_active = False
        hidden.save()
        sold_out.stock = 0
        sold_out.save()
        lines = {l.product.name: l for l in selectors.get_cart_lines(self.store)}
        self.assertTrue(lines["Luffy"].available)
        self.assertFalse(lines["An"].available)
        self.assertFalse(lines["Het"].available)
        self.assertTrue(lines["An"].problem and lines["Het"].problem)
        self.assertEqual(selectors.get_cart_total(list(lines.values())), 1500000)

    def test_ton_kho_giam_xuong_duoi_so_luong_trong_gio(self):
        services.add_item(self.store, self.product.pk, 4)
        self.product.stock = 2
        self.product.save()
        (line,) = selectors.get_cart_lines(self.store)
        self.assertFalse(line.available)
        self.assertIn("2", line.problem)
        self.assertEqual(selectors.get_cart_total([line]), 0)

    def test_so_truy_van_khong_tang_theo_so_dong(self):
        for i in range(2):
            services.add_item(self.store, self.make_product(f"A{i}").pk, 1)
        selectors.get_cart_lines(self.store)
        with CaptureQueriesContext(connection) as few:
            selectors.get_cart_lines(self.store)
        for i in range(2, 7):
            services.add_item(self.store, self.make_product(f"A{i}").pk, 1)
        with CaptureQueriesContext(connection) as many:
            selectors.get_cart_lines(self.store)
        self.assertEqual(len(few), len(many))


class SessionCartTests(StoreContract, CartTestBase):
    def make_store(self):
        self.session = {}
        return SessionCartStore(self.session)

    def test_session_chi_luu_ma_san_pham_va_so_luong(self):
        services.add_item(self.store, self.product.pk, 2)
        self.assertEqual(self.session["cart"], {str(self.product.pk): 2})

    def test_gio_session_khong_canh_bao_doi_gia(self):
        services.add_item(self.store, self.product.pk, 1)
        self.product.price = 2000000
        self.product.save()
        (line,) = selectors.get_cart_lines(self.store)
        self.assertFalse(line.price_changed)
        self.assertEqual(line.unit_price, 2000000)

    def test_du_lieu_session_hong_bi_bo_qua(self):
        self.session["cart"] = {"abc": 1, str(self.product.pk): "x", "0": 2, "-4": 1, "7": -1}
        self.assertEqual(self.store.quantities(), {})
        self.session["cart"] = ["khong", "phai", "dict"]
        self.assertEqual(self.store.quantities(), {})
        self.assertEqual(selectors.get_cart_lines(self.store), [])

    def test_san_pham_da_bi_xoa_khoi_he_thong_thi_bo_dong(self):
        services.add_item(self.store, self.product.pk, 1)
        self.product.delete()
        self.assertEqual(selectors.get_cart_lines(self.store), [])

    def test_hai_session_khac_nhau_khong_dung_chung(self):
        services.add_item(self.store, self.product.pk, 1)
        other = SessionCartStore({})
        self.assertEqual(other.quantities(), {})


class DbCartTests(StoreContract, CartTestBase):
    def make_store(self):
        return DbCartStore(self.user)

    def test_gio_cua_nguoi_dung_khac_khong_bi_anh_huong(self):
        services.add_item(self.store, self.product.pk, 2)
        other = DbCartStore(self.other_user)
        self.assertEqual(other.quantities(), {})
        services.add_item(other, self.product.pk, 1)
        self.assertEqual(self.store.quantities(), {self.product.pk: 2})

    def test_ghi_nho_gia_luc_them(self):
        services.add_item(self.store, self.product.pk, 1)
        self.assertEqual(CartItem.objects.get().unit_price, 1500000)

    def test_gia_doi_thi_canh_bao(self):
        services.add_item(self.store, self.product.pk, 2)
        self.product.price = 1800000
        self.product.save()
        (line,) = selectors.get_cart_lines(self.store)
        self.assertTrue(line.price_changed)
        self.assertEqual(line.old_price, 1500000)
        self.assertEqual(line.unit_price, 1800000)
        self.assertEqual(line.line_total, 3600000)  # luôn tính theo giá hiện tại
        self.assertTrue(line.available)

    def test_gia_khong_doi_thi_khong_canh_bao(self):
        services.add_item(self.store, self.product.pk, 1)
        (line,) = selectors.get_cart_lines(self.store)
        self.assertFalse(line.price_changed)

    def test_them_lai_thi_cap_nhat_gia_moi(self):
        services.add_item(self.store, self.product.pk, 1)
        self.product.price = 1800000
        self.product.save()
        services.add_item(self.store, self.product.pk, 1)
        (line,) = selectors.get_cart_lines(self.store)
        self.assertFalse(line.price_changed)
        self.assertEqual(CartItem.objects.get().unit_price, 1800000)

    def test_sua_so_luong_khong_xoa_canh_bao_doi_gia(self):
        services.add_item(self.store, self.product.pk, 1)
        self.product.price = 1800000
        self.product.save()
        services.set_quantity(self.store, self.product.pk, 2)
        (line,) = selectors.get_cart_lines(self.store)
        self.assertTrue(line.price_changed)

    def test_doc_gio_khong_tao_ban_ghi(self):
        selectors.get_cart_lines(self.store)
        selectors.count_items(self.store)
        from carts.models import Cart
        self.assertEqual(Cart.objects.count(), 0)
