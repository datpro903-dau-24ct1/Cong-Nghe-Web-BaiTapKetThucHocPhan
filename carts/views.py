from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from . import selectors, services
from .stores import store_for_request


def _redirect_back(request):
    """Quay về ?next= nếu là địa chỉ cùng trang web, nếu không thì về trang giỏ hàng."""
    target = request.POST.get("next", "")
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(target)
    return redirect("carts:cart")


def _show_errors(request, error):
    for message in error.messages:
        messages.error(request, message)


def cart_view(request):
    lines = selectors.get_cart_lines(store_for_request(request))
    context = {"lines": lines, "total": selectors.get_cart_total(lines)}
    return render(request, "carts/cart.html", context)


@require_POST
def add_view(request, product_id):
    try:
        services.add_item(store_for_request(request), product_id, request.POST.get("quantity", "1"))
    except ValidationError as error:
        if error.code == "product_unavailable":
            raise Http404("Không tìm thấy sản phẩm.")
        _show_errors(request, error)
    else:
        messages.success(request, "Đã thêm sản phẩm vào giỏ hàng.")
    return _redirect_back(request)


@require_POST
def update_view(request, product_id):
    try:
        services.set_quantity(store_for_request(request), product_id, request.POST.get("quantity"))
    except ValidationError as error:
        _show_errors(request, error)
    else:
        messages.success(request, "Đã cập nhật số lượng.")
    return redirect("carts:cart")


@require_POST
def remove_view(request, product_id):
    services.remove_item(store_for_request(request), product_id)
    messages.success(request, "Đã xóa sản phẩm khỏi giỏ hàng.")
    return redirect("carts:cart")
