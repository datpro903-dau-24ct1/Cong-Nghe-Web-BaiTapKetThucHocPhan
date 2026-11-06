from django.core.validators import MinValueValidator
from django.db import models


class Taxonomy(models.Model):
    """Gốc chung cho Category / Series / Brand: có tên và slug duy nhất."""

    name = models.CharField("Tên", max_length=100, unique=True)
    slug = models.SlugField("Slug", max_length=120, unique=True)

    class Meta:
        abstract = True
        ordering = ["name"]

    def __str__(self):
        return self.name


class Category(Taxonomy):
    class Meta(Taxonomy.Meta):
        verbose_name = "Danh mục"
        verbose_name_plural = "Danh mục"


class Series(Taxonomy):
    class Meta(Taxonomy.Meta):
        verbose_name = "Bộ anime (Series)"
        verbose_name_plural = "Bộ anime (Series)"


class Brand(Taxonomy):
    class Meta(Taxonomy.Meta):
        verbose_name = "Hãng sản xuất"
        verbose_name_plural = "Hãng sản xuất"


class Product(models.Model):
    name = models.CharField("Tên", max_length=200)
    slug = models.SlugField("Slug", max_length=220, unique=True)
    category = models.ForeignKey(
        Category, verbose_name="Danh mục", on_delete=models.PROTECT, related_name="products"
    )
    series = models.ForeignKey(
        Series, verbose_name="Bộ anime", on_delete=models.PROTECT, related_name="products"
    )
    brand = models.ForeignKey(
        Brand, verbose_name="Hãng sản xuất", on_delete=models.PROTECT, related_name="products"
    )
    price = models.DecimalField(
        "Giá (VND)", max_digits=12, decimal_places=0, validators=[MinValueValidator(1)]
    )
    scale = models.CharField("Tỉ lệ", max_length=20, blank=True)
    material = models.CharField("Chất liệu", max_length=100, blank=True)
    height_cm = models.PositiveSmallIntegerField(
        "Chiều cao (cm)", null=True, blank=True, validators=[MinValueValidator(1)]
    )
    stock = models.PositiveIntegerField("Tồn kho", default=0)
    description = models.TextField("Mô tả", blank=True)
    is_active = models.BooleanField("Đang bán", default=True)
    created_at = models.DateTimeField("Ngày tạo", auto_now_add=True)
    updated_at = models.DateTimeField("Ngày cập nhật", auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "Sản phẩm"
        verbose_name_plural = "Sản phẩm"
        constraints = [
            models.CheckConstraint(condition=models.Q(price__gt=0), name="product_price_gt_0"),
        ]

    def __str__(self):
        return self.name


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product, verbose_name="Sản phẩm", on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField("Ảnh", upload_to="products/%Y/%m")
    is_main = models.BooleanField("Ảnh chính", default=False)

    class Meta:
        ordering = ["-is_main", "id"]
        verbose_name = "Ảnh sản phẩm"
        verbose_name_plural = "Ảnh sản phẩm"

    def __str__(self):
        return f"{self.product.name} #{self.pk}"