from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
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
    rating_avg = models.DecimalField(
        "Điểm trung bình", max_digits=3, decimal_places=2, default=0
    )
    review_count = models.PositiveIntegerField("Số đánh giá", default=0)
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

    def clean(self):
        super().clean()
        if self.image:
            from .services import validate_product_image

            validate_product_image(self.image)

    def __str__(self):
        return f"{self.product.name} #{self.pk}"


class Review(models.Model):
    product = models.ForeignKey(
        Product,
        verbose_name="Sản phẩm",
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Người dùng",
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    rating = models.PositiveSmallIntegerField(
        "Số sao",
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    comment = models.TextField("Nhận xét", max_length=2000, blank=True)
    created_at = models.DateTimeField("Ngày đánh giá", auto_now_add=True)
    updated_at = models.DateTimeField("Ngày cập nhật", auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "Đánh giá sản phẩm"
        verbose_name_plural = "Đánh giá sản phẩm"
        constraints = [
            models.UniqueConstraint(
                fields=["product", "user"],
                name="unique_product_user_review",
            ),
            models.CheckConstraint(
                condition=models.Q(rating__gte=1, rating__lte=5),
                name="review_rating_between_1_and_5",
            ),
        ]

    def __str__(self):
        return f"{self.user} - {self.product} ({self.rating}/5)"
