from django.contrib import admin

from .models import Brand, Category, Product, ProductImage, Series


class TaxonomyAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


admin.site.register(Category, TaxonomyAdmin)
admin.site.register(Series, TaxonomyAdmin)
admin.site.register(Brand, TaxonomyAdmin)


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "stock", "category", "series", "brand", "is_active")
    list_filter = ("is_active", "category", "series", "brand")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ProductImageInline]