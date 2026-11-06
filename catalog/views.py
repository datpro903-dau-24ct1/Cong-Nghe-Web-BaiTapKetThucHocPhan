from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from . import selectors, services
from .forms import ProductFilterForm, ReviewForm


def _paginate(request, queryset):
    """Lấy trang theo ?page=; số không hợp lệ về trang 1, số quá lớn về trang cuối."""
    paginator = Paginator(queryset, settings.PRODUCTS_PER_PAGE)
    try:
        number = int(request.GET.get("page", 1))
    except ValueError:
        number = 1
    number = min(max(number, 1), paginator.num_pages)
    return paginator.page(number)


def _report_form_errors(request, form):
    """Đưa lỗi của form lên messages (lỗi từng ô kèm tên ô, lỗi chung đứng riêng)."""
    for field, errors in form.errors.items():
        label = form.fields[field].label if field in form.fields else None
        for error in errors:
            messages.error(request, f"{label}: {error}" if label else error)


FILTER_KEYS = ("q", "series", "brand", "price_min", "price_max", "scale")


def _render_product_list(request, category):
    form = ProductFilterForm(request.GET)
    if form.is_valid():
        filters = form.cleaned_data
    else:
        # Input sai thì báo lỗi và hiển thị danh sách chưa lọc thay vì kết quả sai lệch.
        _report_form_errors(request, form)
        filters = {}
    query = request.GET.copy()
    query.pop("page", None)
    context = {
        "category": category,
        "page_obj": _paginate(request, selectors.search_products(category, **filters)),
        "filter_form": form,
        "is_filtered": any(filters.get(key) not in (None, "") for key in FILTER_KEYS),
        "query_string": query.urlencode(),
        "reset_url": request.path,
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

    has_session_cookie = settings.SESSION_COOKIE_NAME in request.COOKIES
    user = request.user if (has_session_cookie and request.user.is_authenticated) else None
    can_review = selectors.can_user_review_product(user, product) if user else False

    context = {
        "product": product,
        "images": list(product.images.all()),
        "related_products": selectors.list_related_products(product),
        "reviews": selectors.list_product_reviews(product),
        "can_review": can_review,
        "review_form": ReviewForm(),
    }
    return render(request, "catalog/product_detail.html", context)


@login_required
@require_POST
def submit_review_view(request, slug):
    product = selectors.get_active_product_by_slug(slug)
    if product is None:
        raise Http404("Không tìm thấy sản phẩm.")

    form = ReviewForm(request.POST)
    if not form.is_valid():
        _report_form_errors(request, form)
        return redirect("product_detail", slug=product.slug)

    try:
        services.create_review(
            user=request.user,
            product=product,
            rating=form.cleaned_data["rating"],
            comment=form.cleaned_data["comment"],
        )
        messages.success(request, "Cảm ơn bạn đã đánh giá sản phẩm!")
    except ValidationError as exc:
        for msg in exc.messages:
            messages.error(request, msg)

    return redirect("product_detail", slug=product.slug)
