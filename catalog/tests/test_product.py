import io
import tempfile
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase, override_settings
from PIL import Image

from catalog import selectors, services
from catalog.models import Product, ProductImage


def make_image(name="a.png"):
    buf = io.BytesIO()
    Image.new("RGB", (2, 2), "red").save(buf, "PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


class BaseCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = services.create_category("Scale Figure")
        cls.series = services.create_series("One Piece")
        cls.brand = services.create_brand("Good Smile Company")

    def make(self, name="Luffy Gear 5", **kw):
        data = dict(category=self.category, series=self.series, brand=self.brand, price=1500000)
        data.update(kw)
        return services.create_product(name=name, **data)


class CreateProductTests(BaseCase):
    def test_tao_thanh_cong_voi_mac_dinh(self):
        p = self.make(scale="1/7", material="PVC", height_cm=25)
        self.assertEqual(p.slug, "luffy-gear-5")
        self.assertEqual(p.stock, 0)
        self.assertTrue(p.is_active)
        self.assertEqual(p.price, Decimal("1500000"))

    def test_ten_tieng_viet_va_tieng_nhat(self):
        self.assertEqual(self.make("Nendoroid ミク Đồ chơi").slug, "nendoroid-do-choi")

    def test_gia_bang_0_hoac_am_bao_loi(self):
        for bad in (0, -1):
            with self.assertRaises(ValidationError):
                self.make(f"Sp gia {bad}", price=bad)
        self.assertEqual(Product.objects.count(), 0)

    def test_gia_le_bao_loi(self):
        with self.assertRaises(ValidationError):
            self.make(price=Decimal("1000.5"))

    def test_ton_kho_am_bao_loi(self):
        with self.assertRaises(ValidationError):
            self.make(stock=-1)

    def test_chieu_cao_bang_0_bao_loi(self):
        with self.assertRaises(ValidationError):
            self.make(height_cm=0)

    def test_ten_trong_va_slug_rong(self):
        with self.assertRaises(ValidationError) as cm:
            self.make("   ")
        self.assertEqual(cm.exception.code, "blank_name")
        with self.assertRaises(ValidationError) as cm:
            self.make("!!!")
        self.assertEqual(cm.exception.code, "invalid_slug")

    def test_slug_trung_ke_ca_khac_hoa_thuong(self):
        self.make("Luffy")
        with self.assertRaises(ValidationError) as cm:
            self.make("luffy")
        self.assertEqual(cm.exception.code, "duplicate_slug")

    def test_thieu_danh_muc_bao_loi(self):
        with self.assertRaises(ValidationError):
            self.make(category=None)


class ProtectAndConstraintTests(BaseCase):
    def test_khong_xoa_duoc_danh_muc_series_hang_dang_co_san_pham(self):
        self.make()
        for obj in (self.category, self.series, self.brand):
            with self.assertRaises(ProtectedError), transaction.atomic():
                obj.delete()

    def test_csdl_chan_gia_bang_0_du_di_vong_qua_service(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Product.objects.create(
                name="X", slug="x", category=self.category, series=self.series,
                brand=self.brand, price=0,
            )


class ProductImageTests(BaseCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        override = override_settings(MEDIA_ROOT=tmp.name)
        override.enable()
        self.addCleanup(override.disable)
        self.product = self.make()

    def test_san_pham_khong_co_anh_tra_ve_none(self):
        self.assertIsNone(selectors.get_main_image(self.product))

    def test_anh_dau_tien_tu_thanh_anh_chinh(self):
        img = services.add_product_image(self.product, make_image())
        self.assertTrue(img.is_main)
        self.assertEqual(selectors.get_main_image(self.product), img)

    def test_anh_thu_hai_khong_phai_anh_chinh(self):
        first = services.add_product_image(self.product, make_image("1.png"))
        second = services.add_product_image(self.product, make_image("2.png"))
        self.assertFalse(second.is_main)
        self.assertEqual(selectors.get_main_image(self.product), first)

    def test_dat_anh_chinh_moi_bo_anh_chinh_cu(self):
        services.add_product_image(self.product, make_image("1.png"))
        new = services.add_product_image(self.product, make_image("2.png"), is_main=True)
        self.assertEqual(self.product.images.filter(is_main=True).count(), 1)
        self.assertEqual(selectors.get_main_image(self.product), new)

    def test_xoa_san_pham_xoa_luon_anh(self):
        services.add_product_image(self.product, make_image())
        self.product.delete()
        self.assertEqual(ProductImage.objects.count(), 0)