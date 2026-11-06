"""CN10: Gộp giỏ hàng session vào giỏ của user khi đăng nhập / đăng ký."""
from django.urls import reverse

from carts import services
from carts.models import Cart, CartItem
from carts.stores import DbCartStore, SessionCartStore
from carts.tests.base import PASSWORD, CartTestBase


class MergeCartServiceTests(CartTestBase):
    def setUp(self):
        self.session = {}
        self.session_store = SessionCartStore(self.session)
        self.db_store = DbCartStore(self.user)
        self.p1 = self.make_product("Luffy", price=1500000, stock=5)
        self.p2 = self.make_product("Zoro", price=1200000, stock=4)

    def test_gop_gio_session_vao_gio_db_trong(self):
        services.add_item(self.session_store, self.p1.pk, 2)
        services.add_item(self.session_store, self.p2.pk, 1)

        warnings = services.merge_carts(self.session_store, self.db_store)

        self.assertEqual(warnings, [])
        self.assertEqual(self.db_store.quantities(), {self.p1.pk: 2, self.p2.pk: 1})
        self.assertEqual(self.session_store.quantities(), {})
        self.assertNotIn("cart", self.session)

    def test_gop_khi_gio_session_trong_khong_tao_ban_ghi_db(self):
        warnings = services.merge_carts(self.session_store, self.db_store)
        self.assertEqual(warnings, [])
        self.assertEqual(Cart.objects.count(), 0)

    def test_trung_san_pham_thi_cong_don_va_cap_nhat_gia_hien_tai(self):
        services.add_item(self.db_store, self.p1.pk, 2)
        self.p1.price = 1800000
        self.p1.save()
        services.add_item(self.session_store, self.p1.pk, 2)

        warnings = services.merge_carts(self.session_store, self.db_store)

        self.assertEqual(warnings, [])
        self.assertEqual(self.db_store.quantities(), {self.p1.pk: 4})
        self.assertEqual(CartItem.objects.get(product=self.p1).unit_price, 1800000)
        self.assertEqual(self.session_store.quantities(), {})

    def test_tong_vuot_ton_kho_thi_gioi_han_bang_ton_kho_va_canh_bao(self):
        services.add_item(self.db_store, self.p1.pk, 3)
        services.add_item(self.session_store, self.p1.pk, 4)  # tổng 7 > stock 5

        warnings = services.merge_carts(self.session_store, self.db_store)

        self.assertEqual(self.db_store.quantities(), {self.p1.pk: 5})
        self.assertEqual(len(warnings), 1)
        self.assertIn("Luffy", warnings[0])
        self.assertIn("5", warnings[0])
        self.assertEqual(self.session_store.quantities(), {})

    def test_gio_db_da_vuot_ton_kho_tu_truoc_thi_giu_nguyen_so_cu(self):
        services.add_item(self.db_store, self.p1.pk, 5)
        self.p1.stock = 2
        self.p1.save()
        # Session có sẵn trước khi giảm tồn kho
        self.session["cart"] = {str(self.p1.pk): 1}

        warnings = services.merge_carts(self.session_store, self.db_store)

        self.assertEqual(self.db_store.quantities(), {self.p1.pk: 5})
        self.assertEqual(len(warnings), 1)
        self.assertEqual(self.session_store.quantities(), {})

    def test_san_pham_trong_session_het_hang_hoac_bi_an_hoac_da_xoa_bi_bo_qua(self):
        hidden = self.make_product("An", stock=3)
        sold_out = self.make_product("Het", stock=3)
        deleted = self.make_product("Xoa", stock=3)
        deleted_pk = deleted.pk

        services.add_item(self.session_store, hidden.pk, 1)
        services.add_item(self.session_store, sold_out.pk, 1)
        services.add_item(self.session_store, deleted.pk, 1)
        services.add_item(self.session_store, self.p1.pk, 2)

        hidden.is_active = False
        hidden.save()
        sold_out.stock = 0
        sold_out.save()
        deleted.delete()

        warnings = services.merge_carts(self.session_store, self.db_store)

        self.assertEqual(self.db_store.quantities(), {self.p1.pk: 2})
        self.assertNotIn(deleted_pk, self.db_store.quantities())
        self.assertTrue(any("Het" in w for w in warnings))
        self.assertEqual(self.session_store.quantities(), {})

    def test_du_lieu_session_hong_duoc_don_sach_khong_gay_loi(self):
        self.session["cart"] = {"abc": 1, "-2": 3, str(self.p1.pk): "bad"}
        warnings = services.merge_carts(self.session_store, self.db_store)
        self.assertEqual(warnings, [])
        self.assertNotIn("cart", self.session)


class MergeCartOnAuthViewTests(CartTestBase):
    def setUp(self):
        self.p1 = self.make_product("Luffy", price=1500000, stock=5)
        self.p2 = self.make_product("Zoro", price=1200000, stock=4)

    def test_dang_nhap_gop_gio_session_vao_gio_user(self):
        # Đưa sẵn 2 món p1 vào giỏ DB của user
        services.add_item(DbCartStore(self.user), self.p1.pk, 2)

        # Khách vãng lai thêm 1 món p1 và 2 món p2 vào session
        self.client.post(f"/gio-hang/them/{self.p1.pk}/", {"quantity": 1})
        self.client.post(f"/gio-hang/them/{self.p2.pk}/", {"quantity": 2})

        resp = self.client.post(
            reverse("accounts:login"),
            {"email": self.user.email, "password": PASSWORD},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(
            DbCartStore(self.user).quantities(),
            {self.p1.pk: 3, self.p2.pk: 2},
        )
        self.assertNotIn("cart", self.client.session)

    def test_dang_nhap_vuot_ton_kho_hien_canh_bao_va_gioi_han_so_luong(self):
        services.add_item(DbCartStore(self.user), self.p1.pk, 4)
        self.client.post(f"/gio-hang/them/{self.p1.pk}/", {"quantity": 3})

        resp = self.client.post(
            reverse("accounts:login"),
            {"email": self.user.email, "password": PASSWORD},
            follow=True,
        )
        self.assertEqual(DbCartStore(self.user).quantities(), {self.p1.pk: 5})
        self.assertContains(resp, "Luffy")
        self.assertContains(resp, "5")

    def test_dang_ky_moi_cung_gop_gio_session(self):
        self.client.post(f"/gio-hang/them/{self.p1.pk}/", {"quantity": 2})
        resp = self.client.post(
            reverse("accounts:register"),
            {
                "email": "newuser@example.com",
                "full_name": "New User",
                "password": PASSWORD,
                "password_confirm": PASSWORD,
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(CartItem.objects.filter(cart__user__email="newuser@example.com").count(), 1)
        self.assertEqual(
            CartItem.objects.get(cart__user__email="newuser@example.com").quantity,
            2,
        )
        self.assertNotIn("cart", self.client.session)
