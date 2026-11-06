from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db import transaction

from . import services
from .models import Brand, Category, Product, ProductImage, Review, Series


def _is_active_staff(request):
    user = getattr(request, "user", None)
    return bool(user and user.is_authenticated and user.is_active and user.is_staff)


class StaffPermissionAdminMixin:
    """Cho phép nhân viên (is_staff=True) quản lý danh mục và sản phẩm trong /admin/."""

    def has_module_permission(self, request):
        return _is_active_staff(request)

    def has_view_permission(self, request, obj=None):
        return _is_active_staff(request)

    def has_add_permission(self, request, *args, **kwargs):
        return _is_active_staff(request)

    def has_change_permission(self, request, obj=None):
        return _is_active_staff(request)

    def has_delete_permission(self, request, obj=None):
        return _is_active_staff(request)


class TaxonomyAdmin(StaffPermissionAdminMixin, admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


admin.site.register(Category, TaxonomyAdmin)
admin.site.register(Series, TaxonomyAdmin)
admin.site.register(Brand, TaxonomyAdmin)


class ProductImageInline(StaffPermissionAdminMixin, admin.TabularInline):
    model = ProductImage
    extra = 1


class ProductAdminForm(forms.ModelForm):
    """Form quản trị sản phẩm có kiểm tra xung đột chỉnh sửa tồn kho đồng thời (CN15)."""

    initial_stock = forms.IntegerField(widget=forms.HiddenInput, required=False)

    class Meta:
        model = Product
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and not self.is_bound:
            self.initial["initial_stock"] = self.instance.stock

    def clean(self):
        cleaned = super().clean()
        if self.instance and self.instance.pk:
            initial_stock = cleaned.get("initial_stock")
            if initial_stock is not None:
                current_stock = (
                    Product.objects.filter(pk=self.instance.pk)
                    .values_list("stock", flat=True)
                    .first()
                )
                if current_stock is not None and current_stock != initial_stock:
                    raise ValidationError(
                        f"Tồn kho đã thay đổi (từ {initial_stock} thành {current_stock}) bởi thao tác khác. "
                        "Vui lòng tải lại trang trước khi lưu.",
                        code="concurrent_stock_modification",
                    )
        return cleaned


@admin.register(Product)
class ProductAdmin(StaffPermissionAdminMixin, admin.ModelAdmin):
    form = ProductAdminForm
    list_display = (
        "name",
        "price",
        "stock",
        "rating_avg",
        "review_count",
        "category",
        "series",
        "brand",
        "is_active",
    )
    list_filter = ("is_active", "category", "series", "brand")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("rating_avg", "review_count")
    inlines = [ProductImageInline]

    def get_fields(self, request, obj=None):
        fields = list(super().get_fields(request, obj))
        if "initial_stock" not in fields:
            fields.append("initial_stock")
        return fields

    def save_model(self, request, obj, form, change):
        with transaction.atomic():
            if change and obj.pk:
                Product.objects.select_for_update().filter(pk=obj.pk).first()
            super().save_model(request, obj, form, change)


@admin.register(Review)
class ReviewAdmin(StaffPermissionAdminMixin, admin.ModelAdmin):
    list_display = ("product", "user", "rating", "created_at")
    list_filter = ("rating", "created_at")
    search_fields = ("product__name", "user__email", "comment")
    readonly_fields = ("created_at", "updated_at")

    def save_model(self, request, obj, form, change):
        with transaction.atomic():
            super().save_model(request, obj, form, change)
            services.refresh_product_rating_stats(obj.product)

    def delete_model(self, request, obj):
        with transaction.atomic():
            product = obj.product
            super().delete_model(request, obj)
            services.refresh_product_rating_stats(product)

    def delete_queryset(self, request, queryset):
        with transaction.atomic():
            product_ids = list(queryset.values_list("product_id", flat=True).distinct())
            super().delete_queryset(request, queryset)
            for product in Product.objects.filter(pk__in=product_ids):
                services.refresh_product_rating_stats(product)
