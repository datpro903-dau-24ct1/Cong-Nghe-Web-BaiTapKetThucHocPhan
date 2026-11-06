"""Middleware thu hồi phiên đăng nhập ngay khi tài khoản bị khóa (CN17)."""
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import SESSION_KEY, logout
from django.shortcuts import redirect


class ActiveUserMiddleware:
    """Chặn và đăng xuất ngay nếu tài khoản đang có session nhưng bị khóa (is_active=False hoặc locked_until)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            if getattr(user, "is_locked", False):
                logout(request)
                messages.error(
                    request, "Tài khoản của bạn đã bị khóa. Vui lòng liên hệ quản trị viên."
                )
                return redirect(settings.LOGIN_URL)
        elif (
            settings.SESSION_COOKIE_NAME in request.COOKIES
            and SESSION_KEY in request.session
        ):
            # Trường hợp is_active=False làm ModelBackend.get_user trả None nhưng session cũ vẫn còn _auth_user_id.
            logout(request)
            messages.error(
                request, "Tài khoản của bạn đã bị khóa. Vui lòng liên hệ quản trị viên."
            )
            return redirect(settings.LOGIN_URL)

        return self.get_response(request)
