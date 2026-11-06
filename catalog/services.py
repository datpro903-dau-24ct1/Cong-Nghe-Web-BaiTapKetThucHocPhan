"""Nghiệp vụ CRUD Category / Series / Brand / Product, kiểm tra ảnh & đánh giá (CN02, CN03, CN15, CN18).
Lỗi nghiệp vụ -> ValidationError.
"""
import os
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Avg, Count, ProtectedError
from django.utils.text import slugify
from PIL import Image, UnidentifiedImageError

from . import selectors
from .models import Brand, Category, Product, ProductImage, Review, Series

MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_PIL_FORMATS = {"JPEG", "PNG", "WEBP"}


def validate_product_image(image):
    """Kiểm tra dung lượng (≤ 5MB) và định dạng thật của ảnh sản phẩm (JPG, PNG, WEBP)."""
    if image is None:
        raise ValidationError("Vui lòng chọn tệp ảnh.", code="blank_image")

    size = getattr(image, "size", None)
    if size is not None and size > MAX_IMAGE_SIZE_BYTES:
        raise ValidationError(
            "Kích thước ảnh không được vượt quá 5MB.", code="image_too_large"
        )

    ext = os.path.splitext(getattr(image, "name", "") or "")[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError(
            "Định dạng ảnh không hợp lệ (chỉ chấp nhận JPG, PNG, WEBP).",
            code="invalid_image_format",
        )

    try:
        if hasattr(image, "seek"):
            image.seek(0)
        with Image.open(image) as img:
            fmt = img.format
            img.verify()
        if hasattr(image, "seek"):
            image.seek(0)
    except (UnidentifiedImageError, OSError, ValueError):
        raise ValidationError(
            "Định dạng ảnh không hợp lệ (chỉ chấp nhận JPG, PNG, WEBP).",
            code="invalid_image_format",
        )

    if fmt not in ALLOWED_PIL_FORMATS:
        raise ValidationError(
            "Định dạng ảnh không hợp lệ (chỉ chấp nhận JPG, PNG, WEBP).",
            code="invalid_image_format",
        )


def make_slug(name):
    """Tạo slug ASCII từ tên; xử lý riêng chữ Đ/đ vì slugify bỏ mất."""
    return slugify((name or "").replace("Đ", "D").replace("đ", "d"))


def _create(model, name):
    name = (name or "").strip()
    if not name:
        raise ValidationError("Tên không được để trống.", code="blank_name")
    slug = make_slug(name)
    if not slug:
        raise ValidationError("Tên không tạo được slug hợp lệ.", code="invalid_slug")
    if model.objects.filter(slug=slug).exists():
        raise ValidationError(f"Slug '{slug}' đã tồn tại.", code="duplicate_slug")
    obj = model(name=name, slug=slug)
    obj.full_clean()
    obj.save()
    return obj


def create_category(name):
    return _create(Category, name)


def create_series(name):
    return _create(Series, name)


def create_brand(name):
    return _create(Brand, name)


def update_taxonomy(obj, name):
    """Cập nhật tên và slug cho Category / Series / Brand (CN15)."""
    name = (name or "").strip()
    if not name:
        raise ValidationError("Tên không được để trống.", code="blank_name")
    slug = make_slug(name)
    if not slug:
        raise ValidationError("Tên không tạo được slug hợp lệ.", code="invalid_slug")
    model = type(obj)
    if model.objects.filter(slug=slug).exclude(pk=obj.pk).exists():
        raise ValidationError(f"Slug '{slug}' đã tồn tại.", code="duplicate_slug")
    obj.name = name
    obj.slug = slug
    obj.full_clean()
    obj.save()
    return obj


def delete_taxonomy(obj):
    """Xóa một Category / Series / Brand; chặn nếu đang có sản phẩm."""
    try:
        with transaction.atomic():
            obj.delete()
    except ProtectedError:
        raise ValidationError(
            "Không thể xóa mục đang có sản phẩm.", code="in_use"
        )


def bulk_delete_taxonomies(model, ids):
    """Xóa hàng loạt Category / Series / Brand; nếu vướng sản phẩm thì rollback toàn bộ."""
    try:
        with transaction.atomic():
            deleted, _ = model.objects.filter(pk__in=list(ids)).delete()
            return deleted
    except ProtectedError:
        raise ValidationError(
            "Không thể xóa hàng loạt vì có mục đang chứa sản phẩm.", code="in_use"
        )


def create_product(
    *, name, category, series, brand, price, stock=0, scale="", material="",
    height_cm=None, description="", is_active=True,
):
    """Tạo sản phẩm; mọi lỗi dữ liệu đều báo bằng ValidationError."""
    name = (name or "").strip()
    if not name:
        raise ValidationError("Tên sản phẩm không được để trống.", code="blank_name")
    slug = make_slug(name)
    if not slug:
        raise ValidationError("Tên không tạo được slug hợp lệ.", code="invalid_slug")
    if Product.objects.filter(slug=slug).exists():
        raise ValidationError(f"Slug '{slug}' đã tồn tại.", code="duplicate_slug")
    product = Product(
        name=name, slug=slug, category=category, series=series, brand=brand,
        price=price, stock=stock, scale=scale, material=material,
        height_cm=height_cm, description=description, is_active=is_active,
    )
    product.full_clean()
    product.save()
    return product


def update_product(product, *, expected_stock=None, **fields):
    """Cập nhật thông tin sản phẩm, phát hiện xung đột chỉnh sửa tồn kho đồng thời (CN15)."""
    with transaction.atomic():
        locked = Product.objects.select_for_update().get(pk=product.pk)
        if expected_stock is not None and locked.stock != expected_stock:
            raise ValidationError(
                "Tồn kho đã thay đổi bởi thao tác khác. Vui lòng tải lại trước khi lưu.",
                code="concurrent_stock_modification",
            )
        if "name" in fields:
            name = (fields["name"] or "").strip()
            if not name:
                raise ValidationError(
                    "Tên sản phẩm không được để trống.", code="blank_name"
                )
            slug = make_slug(name)
            if not slug:
                raise ValidationError(
                    "Tên không tạo được slug hợp lệ.", code="invalid_slug"
                )
            if Product.objects.filter(slug=slug).exclude(pk=locked.pk).exists():
                raise ValidationError(
                    f"Slug '{slug}' đã tồn tại.", code="duplicate_slug"
                )
            locked.name = name
            locked.slug = slug

        for attr in (
            "category",
            "series",
            "brand",
            "price",
            "stock",
            "scale",
            "material",
            "height_cm",
            "description",
            "is_active",
        ):
            if attr in fields:
                setattr(locked, attr, fields[attr])

        locked.full_clean()
        locked.save()
        return locked


def update_product_stock(product_id, new_stock, *, expected_stock=None):
    """Cập nhật tồn kho có khóa dòng và kiểm tra giá trị cũ để chống ghi đè đồng thời."""
    if isinstance(new_stock, bool) or not isinstance(new_stock, int) or new_stock < 0:
        raise ValidationError("Tồn kho không hợp lệ.", code="invalid_stock")
    with transaction.atomic():
        locked = Product.objects.select_for_update().filter(pk=product_id).first()
        if locked is None:
            raise ValidationError("Không tìm thấy sản phẩm.", code="not_found")
        if expected_stock is not None and locked.stock != expected_stock:
            raise ValidationError(
                "Tồn kho đã thay đổi bởi thao tác khác. Vui lòng tải lại trước khi lưu.",
                code="concurrent_stock_modification",
            )
        locked.stock = new_stock
        locked.save(update_fields=["stock", "updated_at"])
        return locked


def bulk_delete_products(ids):
    """Xóa hàng loạt sản phẩm (và ảnh đính kèm) trong một transaction."""
    with transaction.atomic():
        qs = Product.objects.filter(pk__in=list(ids))
        count = qs.count()
        qs.delete()
        return count


def add_product_image(product, image, is_main=False):
    """Thêm ảnh; kiểm tra dung lượng/định dạng, ảnh đầu tiên tự thành ảnh chính."""
    validate_product_image(image)
    with transaction.atomic():
        Product.objects.select_for_update().get(pk=product.pk)  # khóa để tránh thêm ảnh đồng thời
        make_main = is_main or not product.images.exists()
        if make_main:
            product.images.filter(is_main=True).update(is_main=False)
        return ProductImage.objects.create(product=product, image=image, is_main=make_main)


def refresh_product_rating_stats(product):
    """Tính lại review_count và rating_avg cho sản phẩm."""
    stats = Review.objects.filter(product=product).aggregate(
        cnt=Count("id"),
        avg=Avg("rating"),
    )
    count = stats["cnt"] or 0
    avg_val = stats["avg"]
    if count == 0 or avg_val is None:
        rating_avg = Decimal("0.00")
    else:
        rating_avg = Decimal(str(avg_val)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    product.review_count = count
    product.rating_avg = rating_avg
    product.save(update_fields=["review_count", "rating_avg", "updated_at"])
    return product


def _parse_rating(rating) -> int:
    if isinstance(rating, bool) or rating is None:
        raise ValidationError(
            "Số sao đánh giá phải là số nguyên từ 1 đến 5.", code="invalid_rating"
        )
    if isinstance(rating, str):
        stripped = rating.strip()
        if not stripped.isdigit():
            raise ValidationError(
                "Số sao đánh giá phải là số nguyên từ 1 đến 5.", code="invalid_rating"
            )
        rating = int(stripped)
    if not isinstance(rating, int) or rating < 1 or rating > 5:
        raise ValidationError(
            "Số sao đánh giá phải là số nguyên từ 1 đến 5.", code="invalid_rating"
        )
    return rating


def create_review(*, user, product, rating, comment=""):
    """Tạo đánh giá sản phẩm cho khách hàng đã mua (CN18)."""
    if user is None or not getattr(user, "is_authenticated", False):
        raise ValidationError(
            "Vui lòng đăng nhập để đánh giá sản phẩm.", code="unauthenticated"
        )
    if product is None or not getattr(product, "pk", None):
        raise ValidationError("Sản phẩm không hợp lệ.", code="invalid_product")

    parsed_rating = _parse_rating(rating)
    cleaned_comment = (comment or "").strip()
    if len(cleaned_comment) > 2000:
        raise ValidationError(
            "Nội dung đánh giá không được vượt quá 2000 ký tự.",
            code="comment_too_long",
        )

    if not selectors.has_purchased_product(user, product):
        raise ValidationError(
            "Bạn cần mua sản phẩm này trước khi đánh giá.", code="not_purchased"
        )

    with transaction.atomic():
        locked_product = Product.objects.select_for_update().get(pk=product.pk)
        if Review.objects.filter(product=locked_product, user=user).exists():
            raise ValidationError(
                "Bạn đã đánh giá sản phẩm này rồi.", code="duplicate_review"
            )
        review = Review(
            product=locked_product,
            user=user,
            rating=parsed_rating,
            comment=cleaned_comment,
        )
        review.full_clean()
        try:
            review.save()
        except IntegrityError:
            raise ValidationError(
                "Bạn đã đánh giá sản phẩm này rồi.", code="duplicate_review"
            )
        refresh_product_rating_stats(locked_product)
        product.review_count = locked_product.review_count
        product.rating_avg = locked_product.rating_avg
        return review
