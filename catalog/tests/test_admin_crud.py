"""CN15: Kiểm thử CRUD quản trị (Product, Category, Series, Brand) và các trường hợp biên:
- Upload ảnh quá lớn (> 5MB) / sai định dạng (file giả mạo, định dạng lạ).
- Xóa hàng loạt (chặn khi danh mục/series/hãng đang có sản phẩm; xóa hàng loạt sản phẩm).
- Chỉnh sửa tồn kho đồng thời (phát hiện xung đột ở cả service và form Admin).
"""
import io
import tempfile

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from accounts.models import User
from catalog import services
from catalog.models import Brand, Category, Product, ProductImage, Series

ADMIN_PASS = "Mk-an-toan-123"


def make_valid_image(name="fig.png", fmt="PNG"):
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), "blue").save(buf, fmt)
    return SimpleUploadedFile(name, buf.getvalue(), content_type=f"image/{fmt.lower()}")


class AdminCrudBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser(
            "admin@example.com", ADMIN_PASS, full_name="Admin"
        )
        cls.category = services.create_category("Scale Figure")
        cls.series = services.create_series("One Piece")
        cls.brand = services.create_brand("Good Smile Company")

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        override = override_settings(MEDIA_ROOT=tmp.name)
        override.enable()
        self.addCleanup(override.disable)

    def make_product(self, name="Luffy Gear 5", price=1500000, stock=5, **kw):
        return services.create_product(
            name=name,
            category=kw.pop("category", self.category),
            series=kw.pop("series", self.series),
            brand=kw.pop("brand", self.brand),
            price=price,
            stock=stock,
            **kw,
        )


class ImageValidationTests(AdminCrudBase):
    def test_upload_anh_hop_le_png_jpg_webp(self):
        product = self.make_product()
        for name, fmt in (("a.png", "PNG"), ("b.jpg", "JPEG"), ("c.webp", "WEBP")):
            img = services.add_product_image(product, make_valid_image(name, fmt))
            self.assertIsNotNone(img.pk)

    def test_upload_anh_qua_lon_tren_5mb_bi_chan(self):
        product = self.make_product()
        oversized = SimpleUploadedFile(
            "huge.png",
            b"\x89PNG\r\n\x1a\n" + b"0" * (services.MAX_IMAGE_SIZE_BYTES + 1),
            content_type="image/png",
        )
        with self.assertRaises(ValidationError) as ctx:
            services.add_product_image(product, oversized)
        self.assertEqual(ctx.exception.code, "image_too_large")
        self.assertEqual(ProductImage.objects.count(), 0)

    def test_upload_file_sai_dinh_dang_hoac_gia_mao_duoi_anh_bi_chan(self):
        product = self.make_product()
        fake_png = SimpleUploadedFile(
            "malware.png", b"not an image at all", content_type="image/png"
        )
        txt_file = SimpleUploadedFile(
            "note.txt", b"hello world", content_type="text/plain"
        )
        gif_buf = io.BytesIO()
        Image.new("RGB", (2, 2), "red").save(gif_buf, "GIF")
        gif_file = SimpleUploadedFile(
            "anim.gif", gif_buf.getvalue(), content_type="image/gif"
        )

        for bad_file in (fake_png, txt_file, gif_file):
            with self.assertRaises(ValidationError) as ctx:
                services.add_product_image(product, bad_file)
            self.assertEqual(ctx.exception.code, "invalid_image_format", bad_file.name)
        self.assertEqual(ProductImage.objects.count(), 0)


class ServiceCrudAndBulkTests(AdminCrudBase):
    def test_sua_va_xoa_danh_muc_series_hang_khi_chua_co_san_pham(self):
        cat = services.create_category("Nendoroid")
        updated = services.update_taxonomy(cat, "Nendoroid Doll")
        self.assertEqual(updated.name, "Nendoroid Doll")
        self.assertEqual(updated.slug, "nendoroid-doll")

        services.delete_taxonomy(updated)
        self.assertFalse(Category.objects.filter(pk=cat.pk).exists())

    def test_xoa_hang_loat_danh_muc_dang_co_san_pham_bi_chan_va_rollback(self):
        empty_cat = services.create_category("Chưa có hàng")
        self.make_product("Luffy", category=self.category)

        with self.assertRaises(ValidationError) as ctx:
            services.bulk_delete_taxonomies(Category, [empty_cat.pk, self.category.pk])
        self.assertEqual(ctx.exception.code, "in_use")
        # Cả danh mục trống cũng không bị xóa dở dang nhờ atomic rollback
        self.assertTrue(Category.objects.filter(pk=empty_cat.pk).exists())
        self.assertTrue(Category.objects.filter(pk=self.category.pk).exists())

    def test_xoa_hang_loat_san_pham_thanh_cong(self):
        p1 = self.make_product("SP 1")
        p2 = self.make_product("SP 2")
        p3 = self.make_product("SP 3")
        services.add_product_image(p1, make_valid_image())

        deleted_count = services.bulk_delete_products([p1.pk, p2.pk])
        self.assertEqual(deleted_count, 2)
        self.assertEqual(list(Product.objects.values_list("pk", flat=True)), [p3.pk])
        self.assertEqual(ProductImage.objects.count(), 0)

    def test_cap_nhat_ton_kho_dong_thoi_phat_hien_xung_dot(self):
        product = self.make_product("Luffy", stock=10)
        # Admin A và Admin B cùng đọc thấy stock = 10
        services.update_product_stock(product.pk, 8, expected_stock=10)

        # Admin B vẫn gửi expected_stock=10 -> bị từ chối vì kho thực tế đã là 8
        with self.assertRaises(ValidationError) as ctx:
            services.update_product_stock(product.pk, 15, expected_stock=10)
        self.assertEqual(ctx.exception.code, "concurrent_stock_modification")
        product.refresh_from_db()
        self.assertEqual(product.stock, 8)

    def test_update_product_cap_nhat_thong_tin_va_chan_xung_dot_kho(self):
        product = self.make_product("Luffy", price=1500000, stock=5)
        services.update_product(
            product, name="Luffy Gear 5", price=1800000, stock=7, expected_stock=5
        )
        product.refresh_from_db()
        self.assertEqual(product.name, "Luffy Gear 5")
        self.assertEqual(product.slug, "luffy-gear-5")
        self.assertEqual(product.price, 1800000)
        self.assertEqual(product.stock, 7)

        with self.assertRaises(ValidationError) as ctx:
            services.update_product(product, stock=3, expected_stock=5)
        self.assertEqual(ctx.exception.code, "concurrent_stock_modification")


class DjangoAdminViewTests(AdminCrudBase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def test_mo_danh_sach_admin_cho_product_category_series_brand(self):
        for path in (
            "/admin/catalog/product/",
            "/admin/catalog/category/",
            "/admin/catalog/series/",
            "/admin/catalog/brand/",
        ):
            self.assertEqual(self.client.get(path).status_code, 200, path)

    def test_admin_sua_ton_kho_dong_thoi_bi_chan_khi_kho_da_thay_doi(self):
        product = self.make_product("Luffy", price=1500000, stock=5)
        change_url = f"/admin/catalog/product/{product.pk}/change/"

        # Admin mở trang sửa khi stock đang là 5
        get_resp = self.client.get(change_url)
        self.assertEqual(get_resp.status_code, 200)
        self.assertContains(get_resp, 'name="initial_stock" value="5"')

        # Trong lúc đó khách vừa mua hàng làm stock giảm xuống 3
        Product.objects.filter(pk=product.pk).update(stock=3)

        # Admin bấm Lưu với initial_stock=5 và muốn đặt stock=10 -> bị báo lỗi xung đột
        post_data = {
            "name": product.name,
            "slug": product.slug,
            "category": self.category.pk,
            "series": self.series.pk,
            "brand": self.brand.pk,
            "price": product.price,
            "scale": "",
            "material": "",
            "height_cm": "",
            "stock": 10,
            "initial_stock": 5,
            "description": "",
            "is_active": "on",
            "images-TOTAL_FORMS": 0,
            "images-INITIAL_FORMS": 0,
            "images-MIN_NUM_FORMS": 0,
            "images-MAX_NUM_FORMS": 1000,
        }
        post_resp = self.client.post(change_url, post_data)
        self.assertEqual(post_resp.status_code, 200)
        self.assertContains(post_resp, "Tồn kho đã thay đổi")
        product.refresh_from_db()
        self.assertEqual(product.stock, 3)

    def test_admin_upload_anh_sai_dinh_dang_bi_chan_tren_form(self):
        product = self.make_product("Luffy", price=1500000, stock=5)
        change_url = f"/admin/catalog/product/{product.pk}/change/"
        bad_image = SimpleUploadedFile(
            "bad.png", b"not a valid image", content_type="image/png"
        )
        post_data = {
            "name": product.name,
            "slug": product.slug,
            "category": self.category.pk,
            "series": self.series.pk,
            "brand": self.brand.pk,
            "price": product.price,
            "scale": "",
            "material": "",
            "height_cm": "",
            "stock": 5,
            "initial_stock": 5,
            "description": "",
            "is_active": "on",
            "images-TOTAL_FORMS": 1,
            "images-INITIAL_FORMS": 0,
            "images-MIN_NUM_FORMS": 0,
            "images-MAX_NUM_FORMS": 1000,
            "images-0-image": bad_image,
            "images-0-is_main": "on",
        }
        resp = self.client.post(change_url, post_data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(ProductImage.objects.count(), 0)
