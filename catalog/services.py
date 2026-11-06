"""Nghiệp vụ tạo Category / Series / Brand / Product. Lỗi nghiệp vụ -> ValidationError."""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.text import slugify

from .models import Brand, Category, Product, ProductImage, Series


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


def add_product_image(product, image, is_main=False):
    """Thêm ảnh; ảnh đầu tiên tự thành ảnh chính, mỗi sản phẩm chỉ có một ảnh chính."""
    with transaction.atomic():
        Product.objects.select_for_update().get(pk=product.pk)  # khóa để tránh thêm ảnh đồng thời
        make_main = is_main or not product.images.exists()
        if make_main:
            product.images.filter(is_main=True).update(is_main=False)
        return ProductImage.objects.create(product=product, image=image, is_main=make_main)