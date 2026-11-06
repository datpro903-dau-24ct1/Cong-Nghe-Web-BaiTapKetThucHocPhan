import uuid
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from accounts import selectors as account_selectors
from accounts.permissions import staff_required
from carts import selectors as cart_selectors
from carts.stores import DbCartStore

from . import selectors, services
from .forms import CheckoutForm, DashboardFilterForm
from .models import Order

CART_LEVEL_CODES = {"empty_cart", "product_unavailable", "out_of_stock", "exceeds_stock"}
SESSION_TOKEN_KEY = "checkout_token"
SESSION_COMPLETED_TOKENS_KEY = "completed_checkout_tokens"
ORDERS_PER_PAGE = 10


def _paginate(request, queryset):
    paginator = Paginator(queryset, getattr(settings, "ORDERS_PER_PAGE", ORDERS_PER_PAGE))
    try:
        number = int(request.GET.get("page", 1))
    except ValueError:
        number = 1
    number = min(max(number, 1), paginator.num_pages)
    return paginator.page(number)


def _estimate_shipping_fee(addresses):
    """Ước tính phí vận chuyển hiển thị ban đầu theo địa chỉ mặc định (nếu có)."""
    for addr in addresses:
        if addr.is_default:
            try:
                return services.calculate_shipping_fee(addr.province)
            except ValidationError:
                break
    if addresses:
        try:
            return services.calculate_shipping_fee(addresses[0].province)
        except ValidationError:
            pass
    return services.INNER_SHIPPING_FEE


@login_required
def checkout_view(request):
    # Chống submit trùng: nếu token gửi lên đã tạo đơn thành công trước đó thì về thẳng trang đơn.
    if request.method == "POST":
        submitted_token = (request.POST.get("checkout_token") or "").strip()
        completed_tokens = request.session.get(SESSION_COMPLETED_TOKENS_KEY) or {}
        if submitted_token and submitted_token in completed_tokens:
            existing_order = selectors.get_user_order(
                request.user, completed_tokens[submitted_token]
            )
            if existing_order is not None:
                return redirect("orders:success", order_id=existing_order.pk)

    store = DbCartStore(request.user)
    lines = cart_selectors.get_cart_lines(store)
    if not lines:
        messages.error(request, "Giỏ hàng của bạn đang trống.")
        return redirect("carts:cart")
    if any(not line.available for line in lines):
        messages.error(
            request,
            "Giỏ hàng có sản phẩm không thể đặt (hết hàng hoặc vượt tồn kho). Vui lòng kiểm tra lại.",
        )
        return redirect("carts:cart")

    active_token = request.session.get(SESSION_TOKEN_KEY)
    if not active_token:
        active_token = uuid.uuid4().hex
        request.session[SESSION_TOKEN_KEY] = active_token

    form = (
        CheckoutForm(request.user, request.POST, checkout_token=active_token)
        if request.method == "POST"
        else CheckoutForm(request.user, checkout_token=active_token)
    )
    if request.method == "POST" and form.is_valid():
        try:
            order = services.place_order(
                request.user,
                address_id=form.cleaned_data["address_id"] or None,
                receiver=form.cleaned_data["receiver"],
                phone=form.cleaned_data["phone"],
                street=form.cleaned_data["street"],
                ward=form.cleaned_data["ward"],
                province=form.cleaned_data["province"],
                payment_method=form.cleaned_data["payment_method"],
                coupon_code=form.cleaned_data["coupon_code"],
                note=form.cleaned_data["note"],
            )
        except ValidationError as exc:
            if getattr(exc, "code", None) in CART_LEVEL_CODES:
                for msg in exc.messages:
                    messages.error(request, msg)
                return redirect("carts:cart")
            form.add_error(None, exc)
        else:
            token_used = form.cleaned_data.get("checkout_token") or active_token
            completed = dict(request.session.get(SESSION_COMPLETED_TOKENS_KEY) or {})
            completed[token_used] = order.pk
            request.session[SESSION_COMPLETED_TOKENS_KEY] = completed
            request.session.pop(SESSION_TOKEN_KEY, None)
            messages.success(request, f"Đặt hàng thành công! Mã đơn của bạn là #{order.pk}.")
            return redirect("orders:success", order_id=order.pk)

    addresses = list(account_selectors.list_addresses(request.user))
    subtotal = cart_selectors.get_cart_total(lines)
    shipping_fee = _estimate_shipping_fee(addresses)
    discount_amount = Decimal(0)
    preview_coupon = (request.GET.get("coupon") or "").strip()
    if preview_coupon:
        try:
            _, discount_amount = services.validate_and_calculate_coupon(
                preview_coupon, subtotal
            )
            if not form.is_bound:
                form.initial["coupon_code"] = preview_coupon.upper()
        except ValidationError as exc:
            for msg in exc.messages:
                messages.error(request, msg)

    context = {
        "form": form,
        "lines": lines,
        "subtotal": subtotal,
        "discount_amount": discount_amount,
        "shipping_fee": shipping_fee,
        "total": services.quantize_vnd(subtotal - discount_amount + shipping_fee),
        "addresses": addresses,
    }
    return render(request, "orders/checkout.html", context)


@login_required
def order_success_view(request, order_id):
    order = selectors.get_user_order(request.user, order_id)
    if order is None:
        raise Http404("Không tìm thấy đơn hàng.")
    return render(request, "orders/order_success.html", {"order": order})


@login_required
def order_list_view(request):
    page_obj = _paginate(request, selectors.list_user_orders(request.user))
    return render(request, "orders/order_list.html", {"page_obj": page_obj})


@login_required
def order_detail_view(request, order_id):
    order = selectors.get_user_order(request.user, order_id)
    if order is None:
        raise Http404("Không tìm thấy đơn hàng.")
    context = {
        "order": order,
        "can_cancel": order.status == Order.Status.PENDING,
    }
    return render(request, "orders/order_detail.html", context)


@login_required
@require_POST
def order_cancel_view(request, order_id):
    try:
        services.cancel_order(request.user, order_id)
    except ValidationError as exc:
        if getattr(exc, "code", None) == "order_not_found":
            raise Http404("Không tìm thấy đơn hàng.")
        for msg in exc.messages:
            messages.error(request, msg)
    else:
        messages.success(request, f"Đã hủy đơn hàng #{order_id} và hoàn lại tồn kho.")
    return redirect("orders:detail", order_id=order_id)


@staff_required
def dashboard_view(request):
    form = DashboardFilterForm(request.GET)
    if form.is_valid():
        stats = selectors.get_dashboard_stats(
            start_date=form.cleaned_data.get("start_date"),
            end_date=form.cleaned_data.get("end_date"),
        )
    else:
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
        stats = selectors.get_dashboard_stats()

    context = {
        "filter_form": form,
        "stats": stats,
    }
    return render(request, "orders/dashboard.html", context)
