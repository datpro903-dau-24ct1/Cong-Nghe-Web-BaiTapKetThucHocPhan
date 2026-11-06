"""Các hàm đọc dữ liệu tài khoản (không ghi)."""
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode

from .models import User, clean_email


def list_addresses(user):
    """Địa chỉ của user: mặc định trước, rồi mới nhất trước."""
    return user.addresses.all()


def get_user_address(user, pk):
    """Địa chỉ theo pk nhưng chỉ khi thuộc về user; ngược lại trả về None."""
    return user.addresses.filter(pk=pk).first()


def get_active_user_by_email(email):
    """Tìm người dùng đang hoạt động theo email (chuẩn hóa chữ thường); None nếu không có."""
    normalized = clean_email(email)
    if not normalized:
        return None
    return User.objects.filter(email=normalized, is_active=True).first()


def get_active_user_by_uidb64(uidb64):
    """Giải mã uidb64 và trả về User đang hoạt động; None nếu uidb64 sai định dạng hoặc không tồn tại."""
    try:
        uid = int(force_str(urlsafe_base64_decode(uidb64 or "")))
    except (TypeError, ValueError, OverflowError):
        return None
    return User.objects.filter(pk=uid, is_active=True).first()
