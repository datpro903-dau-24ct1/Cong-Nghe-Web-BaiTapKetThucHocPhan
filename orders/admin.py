from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from . import services
from .models import Coupon, Order, OrderItem, OrderStatusLog


def _is_active_staff(request):
    user = getattr(request, "user", None)
    return bool(user and user.is_authenticated and user.is_active and user.is_staff)


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "discount_type",
        "discount_value",
        "min_order_amount",
        "used_count",
        "usage_limit",
        "valid_from",
        "valid_until",
        "is_active",
    )
    list_filter = ("discount_type", "is_active")
    search_fields = ("code",)
    readonly_fields = ("used_count", "created_at")

    def has_module_permission(self, request):
        return _is_active_staff(request)

    def has_view_permission(self, request, obj=None):
        return _is_active_staff(request)

    def has_add_permission(self, request):
        return _is_active_staff(request)

    def has_change_permission(self, request, obj=None):
        return _is_active_staff(request)

    def has_delete_permission(self, request, obj=None):
        return _is_active_staff(request)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = ("product", "product_name", "unit_price", "quantity", "line_total")

    def has_view_permission(self, request, obj=None):
        return _is_active_staff(request)

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False


class OrderStatusLogInline(admin.TabularInline):
    model = OrderStatusLog
    extra = 0
    can_delete = False
    readonly_fields = ("from_status", "to_status", "changed_by", "note", "created_at")

    def has_view_permission(self, request, obj=None):
        return _is_active_staff(request)

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False


class OrderAdminForm(forms.ModelForm):
    """Form quản trị đơn hàng kiểm tra chuyển trạng thái đúng thứ tự (CN16)."""

    class Meta:
        model = Order
        fields = "__all__"

    def clean_status(self):
        new_status = self.cleaned_data.get("status")
        if self.instance and self.instance.pk:
            current_status = (
                Order.objects.filter(pk=self.instance.pk)
                .values_list("status", flat=True)
                .first()
            )
            if current_status and new_status != current_status:
                if not services.can_transition_order_status(current_status, new_status):
                    old_label = Order.Status(current_status).label
                    new_label = Order.Status(new_status).label
                    raise ValidationError(
                        f"Không thể chuyển trạng thái đơn hàng từ '{old_label}' sang '{new_label}'.",
                        code="invalid_status_transition",
                    )
        return new_status


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    form = OrderAdminForm
    list_display = (
        "id",
        "user",
        "receiver",
        "phone",
        "status",
        "coupon_code",
        "discount_amount",
        "total",
        "created_at",
    )
    list_display_links = ("id", "user", "receiver")
    list_editable = ("status",)
    list_filter = ("status", "payment_method", "created_at")
    search_fields = ("=id", "receiver", "phone", "user__email", "coupon_code")
    actions = [
        "action_mark_confirmed",
        "action_mark_shipping",
        "action_mark_completed",
        "action_mark_cancelled",
    ]
    readonly_fields = (
        "user",
        "receiver",
        "phone",
        "street",
        "ward",
        "district",
        "province",
        "payment_method",
        "coupon",
        "coupon_code",
        "discount_amount",
        "subtotal",
        "shipping_fee",
        "total",
        "created_at",
        "updated_at",
    )
    fields = (
        "user",
        "status",
        "receiver",
        "phone",
        "street",
        "ward",
        "province",
        "payment_method",
        "coupon",
        "coupon_code",
        "discount_amount",
        "subtotal",
        "shipping_fee",
        "total",
        "note",
        "created_at",
        "updated_at",
    )
    inlines = [OrderItemInline, OrderStatusLogInline]

    def get_changelist_form(self, request, **kwargs):
        kwargs.setdefault("form", OrderAdminForm)
        return super().get_changelist_form(request, **kwargs)

    def _run_status_action(self, request, queryset, target_status):
        success_count = 0
        for order in queryset:
            try:
                services.transition_order_status(
                    order.pk,
                    target_status,
                    actor=request.user,
                    note="Cập nhật hàng loạt trong trang quản trị",
                )
                success_count += 1
            except ValidationError as exc:
                for msg in exc.messages:
                    self.message_user(
                        request, f"Đơn #{order.pk}: {msg}", level=messages.ERROR
                    )
        if success_count:
            label = Order.Status(target_status).label
            self.message_user(
                request,
                f"Đã chuyển {success_count} đơn hàng sang trạng thái '{label}'.",
                level=messages.SUCCESS,
            )

    @admin.action(description="Chuyển trạng thái -> Đã xác nhận")
    def action_mark_confirmed(self, request, queryset):
        self._run_status_action(request, queryset, Order.Status.CONFIRMED)

    @admin.action(description="Chuyển trạng thái -> Đang giao")
    def action_mark_shipping(self, request, queryset):
        self._run_status_action(request, queryset, Order.Status.SHIPPING)

    @admin.action(description="Chuyển trạng thái -> Hoàn tất")
    def action_mark_completed(self, request, queryset):
        self._run_status_action(request, queryset, Order.Status.COMPLETED)

    @admin.action(description="Chuyển trạng thái -> Đã hủy (hoàn tồn kho)")
    def action_mark_cancelled(self, request, queryset):
        self._run_status_action(request, queryset, Order.Status.CANCELLED)

    def has_module_permission(self, request):
        return _is_active_staff(request)

    def has_view_permission(self, request, obj=None):
        return _is_active_staff(request)

    def has_change_permission(self, request, obj=None):
        return _is_active_staff(request)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return bool(_is_active_staff(request) and request.user.is_superuser)

    def save_model(self, request, obj, form, change):
        if change and obj.pk:
            current_status = (
                Order.objects.filter(pk=obj.pk)
                .values_list("status", flat=True)
                .first()
            )
            new_status = form.cleaned_data.get("status")
            if current_status and new_status and new_status != current_status:
                updated = services.transition_order_status(
                    obj.pk,
                    new_status,
                    actor=request.user,
                    note="Cập nhật trong trang quản trị",
                )
                obj.status = updated.status
                obj.updated_at = updated.updated_at
                if "note" in form.changed_data:
                    Order.objects.filter(pk=obj.pk).update(note=obj.note)
                return
        super().save_model(request, obj, form, change)
