import re

from django.core.exceptions import ValidationError

_PHONE_RE = re.compile(r"^0[35789][0-9]{8}$")


def normalize_phone(value):
    """Chuẩn hóa số điện thoại Việt Nam về dạng 0xxxxxxxxx (bỏ khoảng trắng, dấu chấm, gạch; +84/84 -> 0)."""
    phone = re.sub(r"[\s.\-()]", "", value or "")
    if phone.startswith("+84"):
        phone = "0" + phone[3:]
    elif phone.startswith("84") and len(phone) == 11:
        phone = "0" + phone[2:]
    return phone


def validate_vn_phone(value):
    if not _PHONE_RE.match(normalize_phone(value)):
        raise ValidationError(
            "Số điện thoại không hợp lệ (ví dụ: 0912345678).", code="invalid_phone"
        )