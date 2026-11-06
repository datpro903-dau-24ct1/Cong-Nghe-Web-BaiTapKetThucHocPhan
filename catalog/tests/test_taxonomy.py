from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from catalog import services
from catalog.models import Brand, Category, Series


class MakeSlugTests(TestCase):
    def test_tieng_viet_co_chu_D(self):
        self.assertEqual(services.make_slug("Đồ chơi Mô hình"), "do-choi-mo-hinh")

    def test_chu_hoa_thuong_nhu_nhau(self):
        self.assertEqual(services.make_slug("Nendoroid"), services.make_slug("nendoroid"))

    def test_toan_ky_tu_dac_biet_cho_slug_rong(self):
        self.assertEqual(services.make_slug("!!!"), "")


class CreateTests(TestCase):
    def test_tao_ca_ba_loai(self):
        self.assertEqual(services.create_category("Figma").slug, "figma")
        self.assertEqual(services.create_series("One Piece").slug, "one-piece")
        self.assertEqual(services.create_brand("Good Smile Company").slug, "good-smile-company")

    def test_ten_duoc_cat_khoang_trang(self):
        self.assertEqual(services.create_category("  Scale Figure  ").name, "Scale Figure")

    def test_ten_trong_bao_loi(self):
        for bad in ("", "   ", None):
            with self.assertRaises(ValidationError) as cm:
                services.create_category(bad)
            self.assertEqual(cm.exception.code, "blank_name")

    def test_ten_khong_tao_duoc_slug(self):
        with self.assertRaises(ValidationError) as cm:
            services.create_brand("!!!")
        self.assertEqual(cm.exception.code, "invalid_slug")

    def test_slug_trung_bao_loi_ke_ca_khac_hoa_thuong(self):
        services.create_series("Naruto")
        with self.assertRaises(ValidationError) as cm:
            services.create_series("naruto")
        self.assertEqual(cm.exception.code, "duplicate_slug")
        self.assertEqual(Series.objects.count(), 1)

    def test_cung_ten_o_hai_loai_khac_nhau_van_duoc(self):
        services.create_category("Nendoroid")
        services.create_brand("Nendoroid")
        self.assertEqual(Category.objects.count(), 1)
        self.assertEqual(Brand.objects.count(), 1)


class ModelTests(TestCase):
    def test_csdl_chan_slug_trung(self):
        Category.objects.create(name="A", slug="a")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Category.objects.create(name="B", slug="a")

    def test_sap_xep_theo_ten_va_str(self):
        services.create_category("Zeta")
        services.create_category("Alpha")
        self.assertEqual([str(c) for c in Category.objects.all()], ["Alpha", "Zeta"])
