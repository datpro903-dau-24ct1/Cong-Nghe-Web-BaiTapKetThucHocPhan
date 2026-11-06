from django import forms
from django.core.exceptions import ValidationError


class RegisterForm(forms.Form):
    email = forms.EmailField(label="Email")
    full_name = forms.CharField(label="Họ và tên", max_length=150)
    password = forms.CharField(label="Mật khẩu", widget=forms.PasswordInput, strip=False)
    password_confirm = forms.CharField(
        label="Nhập lại mật khẩu", widget=forms.PasswordInput, strip=False
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("password") and cleaned.get("password") != cleaned.get("password_confirm"):
            raise ValidationError(
                {"password_confirm": ValidationError("Hai mật khẩu không khớp.", code="mismatch")}
            )
        return cleaned


class LoginForm(forms.Form):
    email = forms.EmailField(label="Email")
    password = forms.CharField(label="Mật khẩu", widget=forms.PasswordInput, strip=False)


class ProfileForm(forms.Form):
    full_name = forms.CharField(label="Họ và tên", max_length=150)
    phone = forms.CharField(label="Số điện thoại", max_length=20, required=False)


class AddressForm(forms.Form):
    receiver = forms.CharField(label="Người nhận", max_length=150)
    phone = forms.CharField(label="Số điện thoại", max_length=20)
    street = forms.CharField(label="Số nhà, tên đường", max_length=255)
    ward = forms.CharField(label="Phường / Xã", max_length=100)
    district = forms.CharField(label="Quận / Huyện", max_length=100)
    province = forms.CharField(label="Tỉnh / Thành phố", max_length=100)
    is_default = forms.BooleanField(label="Đặt làm địa chỉ mặc định", required=False)


class AddressEditForm(AddressForm):
    is_default = None  # đổi địa chỉ mặc định bằng nút riêng trong danh sách


class PasswordResetRequestForm(forms.Form):
    email = forms.EmailField(label="Email đã đăng ký")


class PasswordResetConfirmForm(forms.Form):
    new_password = forms.CharField(
        label="Mật khẩu mới", widget=forms.PasswordInput, strip=False
    )
    new_password_confirm = forms.CharField(
        label="Nhập lại mật khẩu mới", widget=forms.PasswordInput, strip=False
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("new_password") and cleaned.get("new_password") != cleaned.get(
            "new_password_confirm"
        ):
            raise ValidationError(
                {
                    "new_password_confirm": ValidationError(
                        "Hai mật khẩu không khớp.", code="mismatch"
                    )
                }
            )
        return cleaned


class PasswordChangeCustomForm(PasswordResetConfirmForm):
    old_password = forms.CharField(
        label="Mật khẩu hiện tại", widget=forms.PasswordInput, strip=False
    )
    field_order = ["old_password", "new_password", "new_password_confirm"]
