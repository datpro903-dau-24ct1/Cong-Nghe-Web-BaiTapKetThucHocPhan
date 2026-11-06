"""Form kiểm tra input tìm kiếm / lọc / sắp xếp (CN08) và đánh giá sản phẩm (CN18)."""
from django import forms

from . import selectors
from .models import Brand, Series

# Giá lưu trong DecimalField(max_digits=12): số lớn hơn không thể khớp sản phẩm nào.
MAX_PRICE = 10**12 - 1

SORT_CHOICES = [
    ("newest", "Mới nhất"),
    ("price_asc", "Giá tăng dần"),
    ("price_desc", "Giá giảm dần"),
    ("name_asc", "Tên A → Z"),
]


class ProductFilterForm(forms.Form):
    q = forms.CharField(label="Từ khóa", max_length=100, required=False)
    series = forms.ModelChoiceField(
        label="Bộ anime", queryset=Series.objects.all(), to_field_name="slug",
        required=False, empty_label="Tất cả bộ anime",
    )
    brand = forms.ModelChoiceField(
        label="Hãng", queryset=Brand.objects.all(), to_field_name="slug",
        required=False, empty_label="Tất cả hãng",
    )
    price_min = forms.IntegerField(
        label="Giá từ", min_value=0, max_value=MAX_PRICE, required=False,
    )
    price_max = forms.IntegerField(
        label="Giá đến", min_value=0, max_value=MAX_PRICE, required=False,
    )
    scale = forms.ChoiceField(label="Tỉ lệ", required=False)
    sort = forms.ChoiceField(label="Sắp xếp", choices=SORT_CHOICES, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Tỉ lệ là ô chữ tự do trong model nên chỉ cho chọn các giá trị đang có sản phẩm bán.
        scales = selectors.list_scales()
        self.fields["scale"].choices = [("", "Tất cả tỉ lệ")] + [(s, s) for s in scales]

        for name, hint in (
            ("q", "Tìm theo tên sản phẩm..."),
            ("price_min", "Giá từ (VND)"),
            ("price_max", "Giá đến (VND)"),
        ):
            self.fields[name].widget.attrs["placeholder"] = hint

    def clean_q(self):
        return self.cleaned_data["q"].strip()

    def clean(self):
        cleaned = super().clean()
        low, high = cleaned.get("price_min"), cleaned.get("price_max")
        if low is not None and high is not None and low > high:
            raise forms.ValidationError(
                "Giá tối thiểu không được lớn hơn giá tối đa.", code="price_range"
            )
        return cleaned


RATING_CHOICES = [
    (5, "5 sao - Tuyệt vời"),
    (4, "4 sao - Hài lòng"),
    (3, "3 sao - Bình thường"),
    (2, "2 sao - Chưa tốt"),
    (1, "1 sao - Kém"),
]


class ReviewForm(forms.Form):
    rating = forms.IntegerField(
        label="Số sao",
        min_value=1,
        max_value=5,
        initial=5,
        widget=forms.Select(choices=RATING_CHOICES),
        error_messages={
            "required": "Vui lòng chọn số sao đánh giá.",
            "invalid": "Số sao đánh giá phải là số nguyên từ 1 đến 5.",
            "min_value": "Số sao đánh giá phải từ 1 đến 5.",
            "max_value": "Số sao đánh giá phải từ 1 đến 5.",
        },
    )
    comment = forms.CharField(
        label="Nhận xét",
        max_length=2000,
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "Chia sẻ cảm nhận của bạn về mô hình này...",
            }
        ),
    )

    def clean_comment(self):
        return (self.cleaned_data.get("comment") or "").strip()
