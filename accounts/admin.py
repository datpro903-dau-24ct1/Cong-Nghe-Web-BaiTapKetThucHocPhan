from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import BaseUserCreationForm, UserChangeForm

from .models import User


def _is_active_superuser(request):
    user = getattr(request, "user", None)
    return bool(user and user.is_authenticated and user.is_active and user.is_superuser)


class UserAdminCreationForm(BaseUserCreationForm):
    class Meta:
        model = User
        fields = ("email", "full_name")


class UserAdminChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    form = UserAdminChangeForm
    add_form = UserAdminCreationForm
    ordering = ("email",)
    list_display = ("email", "full_name", "is_staff", "is_superuser", "is_active")
    search_fields = ("email", "full_name")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Thông tin", {"fields": ("full_name", "phone")}),
        ("Quyền", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Bảo mật", {"fields": ("failed_login_count", "locked_until", "last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "full_name", "password1", "password2")}),
    )

    def has_module_permission(self, request):
        return _is_active_superuser(request)

    def has_view_permission(self, request, obj=None):
        return _is_active_superuser(request)

    def has_add_permission(self, request):
        return _is_active_superuser(request)

    def has_change_permission(self, request, obj=None):
        return _is_active_superuser(request)

    def has_delete_permission(self, request, obj=None):
        return _is_active_superuser(request)
