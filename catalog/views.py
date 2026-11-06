from django.conf import settings
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import render

from . import selectors


def _paginate(request, queryset):
    """Lấy trang theo ?page=; số không hợp lệ về trang 1, số quá lớn về trang cuối."""
    paginator = Paginator(queryset, settings.PRODUCTS_PER_PAGE)
    try:
        number = int(request.GET.get("page", 1))
    except ValueError:
        number = 1
    number = min(max(number, 1), paginator.num_pages)
    return paginator.page(number)


def _render_product_list(request, category):
    context = {
        "category": category,
        "page_obj": _paginate(request, selectors.list_active_products(category)),
    }
    return render(request, "catalog/product_list.html", context)


def product_list_view(request):
    return _render_product_list(request, None)


def category_view(request, slug):
    category = selectors.get_category_by_slug(slug)
    if category is None:
        raise Http404("Không tìm thấy danh mục.")
    return _render_product_list(request, category)


def product_detail_view(request, slug):
    product = selectors.get_active_product_by_slug(slug)
    if product is None:
        raise Http404("Không tìm thấy sản phẩm.")
    context = {
        "product": product,
        "images": list(product.images.all()),
        "related_products": selectors.list_related_products(product),
    }
    return render(request, "catalog/product_detail.html", context)