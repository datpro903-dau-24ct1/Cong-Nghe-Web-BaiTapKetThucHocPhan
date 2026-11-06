from django.db import IntegrityError, transaction

from carts.models import Cart, CartItem
from carts.tests.base import CartTestBase


class CartModelTests(CartTestBase):
    def test_moi_nguoi_dung_chi_co_mot_gio(self):
        Cart.objects.create(user=self.user)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Cart.objects.create(user=self.user)

    def test_mot_san_pham_chi_co_mot_dong_trong_gio(self):
        cart = Cart.objects.create(user=self.user)
        product = self.make_product()
        CartItem.objects.create(cart=cart, product=product, quantity=1, unit_price=1500000)
        with self.assertRaises(IntegrityError), transaction.atomic():
            CartItem.objects.create(cart=cart, product=product, quantity=2, unit_price=1500000)

    def test_so_luong_phai_tu_1_tro_len(self):
        cart = Cart.objects.create(user=self.user)
        product = self.make_product()
        with self.assertRaises(IntegrityError), transaction.atomic():
            CartItem.objects.create(cart=cart, product=product, quantity=0, unit_price=1500000)

    def test_xoa_san_pham_thi_dong_trong_gio_bi_xoa_theo(self):
        cart = Cart.objects.create(user=self.user)
        product = self.make_product()
        CartItem.objects.create(cart=cart, product=product, quantity=1, unit_price=1500000)
        product.delete()
        self.assertEqual(CartItem.objects.count(), 0)

    def test_xoa_nguoi_dung_thi_xoa_gio(self):
        Cart.objects.create(user=self.other_user)
        self.other_user.delete()
        self.assertEqual(Cart.objects.count(), 0)
