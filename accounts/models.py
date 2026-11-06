from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone

from .validators import validate_vn_phone


def clean_email(value):
    """Chuẩn hóa email: bỏ khoảng trắng và đưa về chữ thường."""
    return (value or "").strip().lower()


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        email = clean_email(email)
        if not email:
            raise ValueError("Email là bắt buộc.")
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields["is_staff"] is not True or extra_fields["is_superuser"] is not True:
            raise ValueError("Superuser phải có is_staff=True và is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField("Email", unique=True)
    full_name = models.CharField("Họ và tên", max_length=150)
    phone = models.CharField(
        "Số điện thoại", max_length=15, blank=True, validators=[validate_vn_phone]
    )
    is_active = models.BooleanField("Đang hoạt động", default=True)
    is_staff = models.BooleanField("Nhân viên", default=False)
    date_joined = models.DateTimeField("Ngày tham gia", default=timezone.now)
    failed_login_count = models.PositiveSmallIntegerField("Số lần đăng nhập sai", default=0)
    locked_until = models.DateTimeField("Khóa đến", null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        verbose_name = "Người dùng"
        verbose_name_plural = "Người dùng"

    def __str__(self):
        return self.email


class Address(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Người dùng",
        on_delete=models.CASCADE,
        related_name="addresses",
    )
    receiver = models.CharField("Người nhận", max_length=150)
    phone = models.CharField("Số điện thoại", max_length=15, validators=[validate_vn_phone])
    street = models.CharField("Số nhà, tên đường", max_length=255)
    ward = models.CharField("Phường / Xã", max_length=100)
    district = models.CharField("Quận / Huyện", max_length=100)
    province = models.CharField("Tỉnh / Thành phố", max_length=100)
    is_default = models.BooleanField("Mặc định", default=False)
    created_at = models.DateTimeField("Ngày tạo", auto_now_add=True)

    class Meta:
        ordering = ["-is_default", "-id"]
        verbose_name = "Địa chỉ giao hàng"
        verbose_name_plural = "Địa chỉ giao hàng"

    def __str__(self):
        return f"{self.receiver} - {self.street}, {self.ward}, {self.district}, {self.province}"