"""Các decorator kiểm tra phân quyền: khách hàng / nhân viên / admin (CN17)."""
from functools import wraps

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect


def staff_required(view_func):
    """Yêu cầu tài khoản nhân viên (is_staff=True) hoặc admin (is_superuser=True)."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return redirect(settings.LOGIN_URL)
        if not user.is_active or getattr(user, "is_locked", False):
            raise PermissionDenied("Tài khoản đã bị khóa.")
        if not (user.is_staff or user.is_superuser):
            raise PermissionDenied("Chỉ nhân viên hoặc quản trị viên mới có quyền truy cập.")
        return view_func(request, *args, **kwargs)

    return _wrapped


def admin_required(view_func):
    """Yêu cầu tài khoản quản trị viên tối cao (is_superuser=True)."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return redirect(settings.LOGIN_URL)
        if not user.is_active or getattr(user, "is_locked", False):
            raise PermissionDenied("Tài khoản đã bị khóa.")
        if not user.is_superuser:
            raise PermissionDenied("Chỉ quản trị viên mới có quyền truy cập.")
        return view_func(request, *args, **kwargs)

    return _wrapped
