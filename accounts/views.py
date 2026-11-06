from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from . import selectors, services
from .forms import AddressEditForm, AddressForm, LoginForm, ProfileForm, RegisterForm


def _safe_next_url(request, next_url):
    """Chỉ chấp nhận đường dẫn nội bộ để tránh chuyển hướng ra trang lạ."""
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return next_url
    return settings.LOGIN_REDIRECT_URL


def register_view(request):
    if request.user.is_authenticated:
        return redirect(settings.LOGIN_REDIRECT_URL)
    form = RegisterForm(request.POST) if request.method == "POST" else RegisterForm()
    if request.method == "POST" and form.is_valid():
        try:
            user = services.register_user(
                email=form.cleaned_data["email"],
                password=form.cleaned_data["password"],
                full_name=form.cleaned_data["full_name"],
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            login(request, user)
            messages.success(request, "Đăng ký thành công. Chào mừng bạn!")
            return redirect(settings.LOGIN_REDIRECT_URL)
    return render(request, "accounts/register.html", {"form": form})


def login_view(request):
    next_url = request.POST.get("next") or request.GET.get("next", "")
    if request.user.is_authenticated:
        return redirect(_safe_next_url(request, next_url))
    form = LoginForm(request.POST) if request.method == "POST" else LoginForm()
    if request.method == "POST" and form.is_valid():
        try:
            user = services.authenticate_user(
                form.cleaned_data["email"], form.cleaned_data["password"]
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            login(request, user)
            return redirect(_safe_next_url(request, next_url))
    return render(request, "accounts/login.html", {"form": form, "next": next_url})


@require_POST
def logout_view(request):
    logout(request)
    messages.info(request, "Bạn đã đăng xuất.")
    return redirect(settings.LOGOUT_REDIRECT_URL)


# ---------------------------------------------------------------- CN05: hồ sơ và sổ địa chỉ


def _get_address_or_404(request, pk):
    address = selectors.get_user_address(request.user, pk)
    if address is None:
        raise Http404("Không tìm thấy địa chỉ.")
    return address


@login_required
def profile_view(request):
    if request.method == "POST":
        form = ProfileForm(request.POST)
        if form.is_valid():
            try:
                services.update_profile(
                    request.user,
                    full_name=form.cleaned_data["full_name"],
                    phone=form.cleaned_data["phone"],
                )
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(request, "Đã cập nhật hồ sơ.")
                return redirect("accounts:profile")
    else:
        form = ProfileForm(
            initial={"full_name": request.user.full_name, "phone": request.user.phone}
        )
    return render(request, "accounts/profile.html", {"form": form})


@login_required
def address_list_view(request):
    addresses = selectors.list_addresses(request.user)
    return render(request, "accounts/address_list.html", {"addresses": addresses})


@login_required
def address_create_view(request):
    form = AddressForm(request.POST) if request.method == "POST" else AddressForm()
    if request.method == "POST" and form.is_valid():
        try:
            services.create_address(request.user, **form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Đã thêm địa chỉ giao hàng.")
            return redirect("accounts:address_list")
    return render(request, "accounts/address_form.html", {"form": form, "title": "Thêm địa chỉ"})


@login_required
def address_edit_view(request, pk):
    address = _get_address_or_404(request, pk)
    if request.method == "POST":
        form = AddressEditForm(request.POST)
        if form.is_valid():
            try:
                services.update_address(address, **form.cleaned_data)
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(request, "Đã cập nhật địa chỉ.")
                return redirect("accounts:address_list")
    else:
        form = AddressEditForm(
            initial={
                "receiver": address.receiver,
                "phone": address.phone,
                "street": address.street,
                "ward": address.ward,
                "district": address.district,
                "province": address.province,
            }
        )
    return render(request, "accounts/address_form.html", {"form": form, "title": "Sửa địa chỉ"})


@login_required
@require_POST
def address_delete_view(request, pk):
    services.delete_address(_get_address_or_404(request, pk))
    messages.success(request, "Đã xóa địa chỉ.")
    return redirect("accounts:address_list")


@login_required
@require_POST
def address_set_default_view(request, pk):
    services.set_default_address(_get_address_or_404(request, pk))
    messages.success(request, "Đã đặt làm địa chỉ mặc định.")
    return redirect("accounts:address_list")