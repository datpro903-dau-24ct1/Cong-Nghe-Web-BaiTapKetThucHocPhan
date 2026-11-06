"""Form đặt hàng (CN12, CN13, CN22) và lọc thống kê Dashboard (CN25)."""
from django import forms
from django.core.exceptions import ValidationError

from accounts import selectors as account_selectors

from .models import Order


class CheckoutForm(forms.Form):
    address_id = forms.ChoiceField(
        label="Địa chỉ từ sổ địa chỉ", required=False
    )
    receiver = forms.CharField(
        label="Người nhận", max_length=150, required=False
    )
    phone = forms.CharField(
        label="Số điện thoại", max_length=20, required=False
    )
    street = forms.CharField(
        label="Số nhà, tên đường", max_length=255, required=False
    )
    ward = forms.CharField(
        label="Phường / Xã", max_length=100, required=False
    )
    province = forms.CharField(
        label="Tỉnh / Thành phố", max_length=100, required=False
    )
    payment_method = forms.ChoiceField(
        label="Phương thức thanh toán",
        choices=Order.PaymentMethod.choices,
        initial=Order.PaymentMethod.COD,
        required=False,
    )
    coupon_code = forms.CharField(
        label="Mã giảm giá (nếu có)",
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Nhập 1 mã giảm giá (VD: ANIME15)..."}),
    )
    note = forms.CharField(
        label="Ghi chú đơn hàng",
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Ghi chú khi giao hàng (nếu có)..."}),
    )
    checkout_token = forms.CharField(widget=forms.HiddenInput, required=False)

    def __init__(self, user, *args, checkout_token="", **kwargs):
        super().__init__(*args, **kwargs)
        addresses = list(account_selectors.list_addresses(user))
        choices = [("", "— Nhập địa chỉ giao hàng mới bên dưới —")]
        default_id = ""
        for addr in addresses:
            summary = f"{addr.receiver} ({addr.phone}) - {addr.street}, {addr.ward}, {addr.province}"
            choices.append((str(addr.pk), summary))
            if addr.is_default and not default_id:
                default_id = str(addr.pk)
        if not default_id and addresses:
            default_id = str(addresses[0].pk)
        self.fields["address_id"].choices = choices
        if not self.is_bound:
            self.initial.setdefault("address_id", default_id)
            self.initial.setdefault("receiver", user.full_name)
            self.initial.setdefault("phone", user.phone)
            self.initial.setdefault("payment_method", Order.PaymentMethod.COD)
            if checkout_token:
                self.initial["checkout_token"] = checkout_token

    def clean_payment_method(self):
        value = self.cleaned_data.get("payment_method")
        return value or Order.PaymentMethod.COD

    def clean_coupon_code(self):
        return (self.cleaned_data.get("coupon_code") or "").strip()


class DashboardFilterForm(forms.Form):
    start_date = forms.DateField(
        label="Từ ngày",
        required=False,
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(attrs={"type": "date"}),
        error_messages={"invalid": "Ngày bắt đầu không hợp lệ (định dạng YYYY-MM-DD)."},
    )
    end_date = forms.DateField(
        label="Đến ngày",
        required=False,
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(attrs={"type": "date"}),
        error_messages={"invalid": "Ngày kết thúc không hợp lệ (định dạng YYYY-MM-DD)."},
    )

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")
        if start and end and start > end:
            raise ValidationError(
                "Ngày bắt đầu không được lớn hơn ngày kết thúc.",
                code="invalid_date_range",
            )
        return cleaned
