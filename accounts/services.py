"""Nghiệp vụ tài khoản. Lỗi nghiệp vụ -> ValidationError. Không phụ thuộc request/View."""
import math
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from . import selectors
from .models import Address, User, clean_email
from .validators import normalize_phone, validate_vn_phone

MAX_FAILED_LOGINS = 5
LOCK_MINUTES = 15


def register_user(*, email, password, full_name):
    """Đăng ký tài khoản mới. Lỗi được gắn theo tên trường: email, full_name, password."""
    email = clean_email(email)
    full_name = (full_name or "").strip()
    errors = {}

    try:
        validate_email(email)
    except ValidationError:
        errors["email"] = ValidationError("Email không hợp lệ.", code="invalid_email")
    else:
        if User.objects.filter(email=email).exists():
            errors["email"] = ValidationError("Email này đã được đăng ký.", code="duplicate_email")

    if not full_name:
        errors["full_name"] = ValidationError("Họ tên không được để trống.", code="blank_full_name")
    elif len(full_name) > 150:
        errors["full_name"] = ValidationError("Họ tên tối đa 150 ký tự.", code="full_name_too_long")

    try:
        validate_password(password or "", user=User(email=email, full_name=full_name))
    except ValidationError as exc:
        errors["password"] = exc

    if errors:
        raise ValidationError(errors)

    try:
        with transaction.atomic():
            return User.objects.create_user(email=email, password=password, full_name=full_name)
    except IntegrityError:  # hai người đăng ký cùng email cùng lúc
        raise ValidationError(
            {"email": ValidationError("Email này đã được đăng ký.", code="duplicate_email")}
        )


def authenticate_user(email, password):
    """Xác thực email + mật khẩu; khóa tạm tài khoản sau nhiều lần sai liên tiếp."""
    email = clean_email(email)
    error = None
    authenticated = None

    with transaction.atomic():
        user = User.objects.select_for_update().filter(email=email).first()
        now = timezone.now()

        if user is not None and user.locked_until and user.locked_until > now:
            minutes = math.ceil((user.locked_until - now).total_seconds() / 60)
            error = ValidationError(
                f"Đăng nhập sai quá nhiều lần. Vui lòng thử lại sau {minutes} phút.",
                code="locked",
            )
        else:
            authenticated = authenticate(email=email, password=password)
            if authenticated is None:
                if user is not None:
                    user.failed_login_count += 1
                    if user.failed_login_count >= MAX_FAILED_LOGINS:
                        user.locked_until = now + timedelta(minutes=LOCK_MINUTES)
                        user.failed_login_count = 0
                    user.save(update_fields=["failed_login_count", "locked_until"])
                error = ValidationError(
                    "Email hoặc mật khẩu không đúng.", code="invalid_credentials"
                )
            elif user.failed_login_count or user.locked_until:
                user.failed_login_count = 0
                user.locked_until = None
                user.save(update_fields=["failed_login_count", "locked_until"])

    # raise ngoài khối atomic để bộ đếm sai không bị rollback
    if error is not None:
        raise error
    return authenticated


def update_profile(user, *, full_name, phone=""):
    """Cập nhật họ tên và số điện thoại (SĐT được chuẩn hóa về dạng 0xxxxxxxxx)."""
    full_name = (full_name or "").strip()
    phone = normalize_phone(phone)
    errors = {}

    if not full_name:
        errors["full_name"] = ValidationError("Họ tên không được để trống.", code="blank_full_name")
    elif len(full_name) > 150:
        errors["full_name"] = ValidationError("Họ tên tối đa 150 ký tự.", code="full_name_too_long")

    if phone:
        try:
            validate_vn_phone(phone)
        except ValidationError as exc:
            errors["phone"] = exc

    if errors:
        raise ValidationError(errors)

    user.full_name = full_name
    user.phone = phone
    user.save(update_fields=["full_name", "phone"])
    return user


def _clean_address_fields(receiver, phone, street, ward, district, province):
    return {
        "receiver": (receiver or "").strip(),
        "phone": normalize_phone(phone),
        "street": (street or "").strip(),
        "ward": (ward or "").strip(),
        "district": (district or "").strip(),
        "province": (province or "").strip(),
    }


def create_address(
    user, *, receiver, phone, street, ward, district, province, is_default=False
):
    """Thêm địa chỉ. Địa chỉ đầu tiên tự thành mặc định; mỗi người chỉ có một địa chỉ mặc định."""
    address = Address(
        user=user, **_clean_address_fields(receiver, phone, street, ward, district, province)
    )
    address.full_clean()
    with transaction.atomic():
        User.objects.select_for_update().get(pk=user.pk)  # khóa để tránh hai địa chỉ mặc định
        if is_default or not Address.objects.filter(user=user).exists():
            Address.objects.filter(user=user, is_default=True).update(is_default=False)
            address.is_default = True
        address.save()
    return address


def update_address(address, *, receiver, phone, street, ward, district, province):
    """Sửa thông tin địa chỉ (không đổi trạng thái mặc định)."""
    fields = _clean_address_fields(receiver, phone, street, ward, district, province)
    for name, value in fields.items():
        setattr(address, name, value)
    address.full_clean()
    address.save(update_fields=list(fields))
    return address


def set_default_address(address):
    """Đặt địa chỉ làm mặc định và bỏ mặc định của các địa chỉ còn lại."""
    with transaction.atomic():
        User.objects.select_for_update().get(pk=address.user_id)
        Address.objects.filter(user_id=address.user_id, is_default=True).exclude(
            pk=address.pk
        ).update(is_default=False)
        Address.objects.filter(pk=address.pk).update(is_default=True)
    address.is_default = True
    return address


def delete_address(address):
    """Xóa địa chỉ; nếu xóa địa chỉ mặc định thì địa chỉ mới nhất còn lại thành mặc định."""
    with transaction.atomic():
        User.objects.select_for_update().get(pk=address.user_id)
        current = Address.objects.filter(pk=address.pk).first()
        if current is None:
            return
        was_default = current.is_default
        current.delete()
        if was_default:
            replacement = Address.objects.filter(user_id=address.user_id).order_by("-id").first()
            if replacement is not None:
                replacement.is_default = True
                replacement.save(update_fields=["is_default"])


# ---------------------------------------------------------------- CN19: quên mật khẩu / đổi mật khẩu


def request_password_reset(
    email,
    *,
    reset_url_builder,
    send_mail_fn,
    token_generator=default_token_generator,
) -> bool:
    """Tạo token đặt lại mật khẩu và gửi email qua hàm truyền vào (CN19).

    Nếu email không tồn tại hoặc tài khoản bị vô hiệu hóa thì trả về False
    mà không báo lỗi để không tiết lộ thông tin tài khoản.
    """
    user = selectors.get_active_user_by_email(email)
    if user is None:
        return False

    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = token_generator.make_token(user)
    reset_url = reset_url_builder(uidb64, token)

    subject = "Đặt lại mật khẩu - Anime Figure Shop"
    message = (
        f"Xin chào {user.full_name},\n\n"
        f"Bạn (hoặc ai đó) vừa yêu cầu đặt lại mật khẩu cho tài khoản {user.email}.\n"
        f"Vui lòng mở liên kết dưới đây để đặt mật khẩu mới:\n{reset_url}\n\n"
        "Nếu bạn không yêu cầu, vui lòng bỏ qua email này."
    )
    send_mail_fn(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
    )
    return True


def verify_password_reset_token(
    uidb64, token, *, token_generator=default_token_generator
):
    """Kiểm tra uidb64 + token đặt lại mật khẩu; không hợp lệ/hết hạn -> ValidationError."""
    user = selectors.get_active_user_by_uidb64(uidb64)
    if user is None or not token or not token_generator.check_token(user, token):
        raise ValidationError(
            "Liên kết đặt lại mật khẩu không hợp lệ hoặc đã hết hạn.",
            code="invalid_token",
        )
    return user


def reset_password_with_token(
    uidb64,
    token,
    *,
    new_password,
    token_generator=default_token_generator,
):
    """Đặt lại mật khẩu bằng token; sau khi đổi mật khẩu token cũ tự mất hiệu lực."""
    user = verify_password_reset_token(
        uidb64, token, token_generator=token_generator
    )
    try:
        validate_password(new_password or "", user=user)
    except ValidationError as exc:
        raise ValidationError({"new_password": exc})

    with transaction.atomic():
        locked = User.objects.select_for_update().get(pk=user.pk)
        if not token_generator.check_token(locked, token):
            raise ValidationError(
                "Liên kết đặt lại mật khẩu không hợp lệ hoặc đã hết hạn.",
                code="invalid_token",
            )
        locked.set_password(new_password)
        locked.failed_login_count = 0
        locked.locked_until = None
        locked.save(update_fields=["password", "failed_login_count", "locked_until"])
        return locked


def change_password(user, *, old_password, new_password):
    """Đổi mật khẩu cho người dùng đang đăng nhập."""
    if user is None or not getattr(user, "is_authenticated", False):
        raise ValidationError("Vui lòng đăng nhập.", code="unauthenticated")

    errors = {}
    if not user.check_password(old_password or ""):
        errors["old_password"] = ValidationError(
            "Mật khẩu hiện tại không đúng.", code="invalid_old_password"
        )

    try:
        validate_password(new_password or "", user=user)
    except ValidationError as exc:
        errors["new_password"] = exc

    if errors:
        raise ValidationError(errors)

    with transaction.atomic():
        user.set_password(new_password)
        user.save(update_fields=["password"])
    return user
