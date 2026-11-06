"""Dữ liệu dùng chung cho test giỏ hàng (CN09)."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from catalog import services as catalog_services

PASSWORD = "Matkhau!2345"


class CartTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = catalog_services.create_category("Scale Figure")
        cls.series = catalog_services.create_series("One Piece")
        cls.brand = catalog_services.create_brand("Good Smile Company")
        User = get_user_model()
        cls.user = User.objects.create_user("an@example.com", PASSWORD, full_name="An")
        cls.other_user = User.objects.create_user("binh@example.com", PASSWORD, full_name="Binh")

    def make_product(self, name="Luffy", price=1500000, stock=5, **kw):
        return catalog_services.create_product(
            name=name, category=self.category, series=self.series, brand=self.brand,
            price=price, stock=stock, **kw,
        )
