from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts import selectors, services
from accounts.models import Address, User
from accounts.validators import normalize_phone, validate_vn_phone

GOOD = "Mk-an-toan-123"

ADDR = dict(
    receiver="Nguyễn Văn A", phone="0912345678", street="12 Lê Lợi",
    ward="Bến Nghé", district="Quận 1", province="TP. Hồ Chí Minh",
)


def default_ids(user):
    return list(Address.objects.filter(user=user, is_default=True).values_list("id", flat=True))


class PhoneTests(TestCase):
    def test_chuan_hoa(self):
        for raw in ("0912345678", "+84 912 345 678", "84912345678", "091.234.5678", "(091) 234-5678"):
            self.assertEqual(normalize_phone(raw), "0912345678", raw)

    def test_hop_le(self):
        for ok in ("0912345678", "0312345678", "0587654321", "0771234567", "0861234567", "+84912345678"):
            validate_vn_phone(ok)

    def test_khong_hop_le(self):
        bad = (
            "", "abc", "091234567", "09123456789", "0212345678", "0112345678",
            "1912345678", "09a2345678", "٠٩١٢٣٤٥٦٧٨", "+8491234567",
        )
        for value in bad:
            with self.assertRaises(ValidationError, msg=value) as cm:
                validate_vn_phone(value)
            self.assertEqual(cm.exception.code, "invalid_phone")


class UpdateProfileTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("a@example.com", GOOD, full_name="A")

    def test_cap_nhat_va_chuan_hoa_sdt(self):
        services.update_profile(self.user, full_name="  Nguyễn A ", phone="+84 912 345 678")
        self.user.refresh_from_db()
        self.assertEqual((self.user.full_name, self.user.phone), ("Nguyễn A", "0912345678"))

    def test_cho_phep_bo_trong_sdt(self):
        services.update_profile(self.user, full_name="A", phone="0912345678")
        services.update_profile(self.user, full_name="A", phone="")
        self.user.refresh_from_db()
        self.assertEqual(self.user.phone, "")

    def test_sdt_sai_khong_luu_gi(self):
        with self.assertRaises(ValidationError) as cm:
            services.update_profile(self.user, full_name="Tên mới", phone="123")
        self.assertIn("phone", cm.exception.error_dict)
        self.user.refresh_from_db()
        self.assertEqual(self.user.full_name, "A")

    def test_ho_ten_trong_hoac_qua_dai(self):
        for bad in ("   ", "x" * 151):
            with self.assertRaises(ValidationError) as cm:
                services.update_profile(self.user, full_name=bad, phone="")
            self.assertIn("full_name", cm.exception.error_dict)


class AddressServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("a@example.com", GOOD, full_name="A")
        self.other = User.objects.create_user("b@example.com", GOOD, full_name="B")

    def add(self, user=None, **kw):
        data = dict(ADDR)
        data.update(kw)
        return services.create_address(user or self.user, **data)

    def test_dia_chi_dau_tien_tu_thanh_mac_dinh(self):
        a = self.add()
        self.assertTrue(a.is_default)

    def test_dia_chi_thu_hai_khong_phai_mac_dinh(self):
        first, second = self.add(), self.add(street="34 Hai Bà Trưng")
        self.assertEqual(default_ids(self.user), [first.id])
        self.assertFalse(second.is_default)

    def test_them_dia_chi_mac_dinh_moi_bo_mac_dinh_cu(self):
        self.add()
        new = self.add(street="34 Hai Bà Trưng", is_default=True)
        self.assertEqual(default_ids(self.user), [new.id])

    def test_mac_dinh_cua_nguoi_khac_khong_bi_anh_huong(self):
        self.add()
        theirs = self.add(user=self.other)
        self.add(street="x", is_default=True)
        self.assertEqual(default_ids(self.other), [theirs.id])

    def test_dat_mac_dinh(self):
        a, b = self.add(), self.add(street="34 Hai Bà Trưng")
        services.set_default_address(b)
        self.assertEqual(default_ids(self.user), [b.id])
        services.set_default_address(a)
        self.assertEqual(default_ids(self.user), [a.id])

    def test_xoa_dia_chi_mac_dinh_thi_dia_chi_moi_nhat_len_thay(self):
        a = self.add()
        b = self.add(street="b")
        c = self.add(street="c")
        services.delete_address(a)
        self.assertEqual(default_ids(self.user), [c.id])
        self.assertTrue(Address.objects.filter(pk=b.pk, is_default=False).exists())

    def test_xoa_dia_chi_khong_mac_dinh_giu_nguyen_mac_dinh(self):
        a, b = self.add(), self.add(street="b")
        services.delete_address(b)
        self.assertEqual(default_ids(self.user), [a.id])

    def test_xoa_dia_chi_cuoi_cung(self):
        a = self.add()
        services.delete_address(a)
        self.assertEqual(Address.objects.filter(user=self.user).count(), 0)

    def test_xoa_hai_lan_khong_loi(self):
        a = self.add()
        services.delete_address(a)
        services.delete_address(a)

    def test_luon_chi_co_mot_mac_dinh_sau_chuoi_thao_tac(self):
        items = [self.add(street=str(i), is_default=(i % 2 == 0)) for i in range(5)]
        services.set_default_address(items[1])
        services.delete_address(items[1])
        services.delete_address(items[4])
        self.add(street="moi", is_default=True)
        self.assertEqual(len(default_ids(self.user)), 1)

    def test_du_lieu_sai(self):
        for field, bad in (
            ("receiver", "  "), ("phone", "123"), ("street", ""), ("ward", ""),
            ("district", ""), ("province", ""), ("receiver", "x" * 151),
        ):
            with self.assertRaises(ValidationError, msg=f"{field}={bad!r}") as cm:
                self.add(**{field: bad})
            self.assertIn(field, cm.exception.error_dict)
        self.assertEqual(Address.objects.count(), 0)

    def test_sdt_duoc_chuan_hoa_khi_luu(self):
        self.assertEqual(self.add(phone="+84 912 345 678").phone, "0912345678")

    def test_sua_khong_doi_mac_dinh(self):
        a = self.add()
        fields = dict(ADDR, street="Địa chỉ mới")
        services.update_address(a, **fields)
        a.refresh_from_db()
        self.assertEqual(a.street, "Địa chỉ mới")
        self.assertTrue(a.is_default)

    def test_sua_sai_khong_luu(self):
        a = self.add()
        with self.assertRaises(ValidationError):
            services.update_address(a, **dict(ADDR, phone="abc"))
        a.refresh_from_db()
        self.assertEqual(a.phone, "0912345678")

    def test_selector_chi_tra_dia_chi_cua_chinh_user(self):
        mine, theirs = self.add(), self.add(user=self.other)
        self.assertEqual(selectors.get_user_address(self.user, mine.pk), mine)
        self.assertIsNone(selectors.get_user_address(self.user, theirs.pk))
        self.assertEqual(list(selectors.list_addresses(self.user)), [mine])

    def test_xoa_user_xoa_luon_dia_chi(self):
        self.add()
        self.user.delete()
        self.assertEqual(Address.objects.count(), 0)


class ProfileViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("a@example.com", GOOD, full_name="A")
        self.other = User.objects.create_user("b@example.com", GOOD, full_name="B")
        self.client.force_login(self.user)

    def test_chua_dang_nhap_bi_chuyen_ve_trang_dang_nhap(self):
        self.client.logout()
        for url in ("/accounts/profile/", "/accounts/addresses/", "/accounts/addresses/add/"):
            resp = self.client.get(url)
            self.assertRedirects(resp, f"/accounts/login/?next={url}")

    def test_xem_va_sua_ho_so(self):
        self.assertContains(self.client.get("/accounts/profile/"), "a@example.com")
        resp = self.client.post("/accounts/profile/", {"full_name": "Tên mới", "phone": "0912 345 678"})
        self.assertRedirects(resp, "/accounts/profile/")
        self.user.refresh_from_db()
        self.assertEqual((self.user.full_name, self.user.phone), ("Tên mới", "0912345678"))

    def test_sdt_sai_hien_loi(self):
        resp = self.client.post("/accounts/profile/", {"full_name": "A", "phone": "123"})
        self.assertContains(resp, "Số điện thoại không hợp lệ")


class AddressViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("a@example.com", GOOD, full_name="A")
        self.other = User.objects.create_user("b@example.com", GOOD, full_name="B")
        self.theirs = services.create_address(self.other, **ADDR)
        self.client.force_login(self.user)

    def post_add(self, **kw):
        data = dict(ADDR)
        data.update(kw)
        return self.client.post("/accounts/addresses/add/", data)

    def test_them_dia_chi_dau_tien_la_mac_dinh(self):
        self.assertRedirects(self.post_add(), "/accounts/addresses/")
        self.assertEqual(self.user.addresses.get().is_default, True)

    def test_them_voi_o_mac_dinh(self):
        self.post_add()
        self.post_add(street="Mới", is_default="on")
        self.assertEqual(self.user.addresses.get(is_default=True).street, "Mới")

    def test_them_sai_hien_loi_va_khong_luu(self):
        resp = self.post_add(phone="123")
        self.assertContains(resp, "Số điện thoại không hợp lệ")
        self.assertEqual(self.user.addresses.count(), 0)

    def test_sua_dia_chi(self):
        mine = services.create_address(self.user, **ADDR)
        resp = self.client.get(f"/accounts/addresses/{mine.pk}/edit/")
        self.assertContains(resp, "12 Lê Lợi")
        self.client.post(f"/accounts/addresses/{mine.pk}/edit/", dict(ADDR, street="Đã sửa"))
        mine.refresh_from_db()
        self.assertEqual(mine.street, "Đã sửa")

    def test_dat_mac_dinh_va_xoa_bang_post(self):
        a = services.create_address(self.user, **ADDR)
        b = services.create_address(self.user, **dict(ADDR, street="b"))
        self.client.post(f"/accounts/addresses/{b.pk}/default/")
        self.assertEqual(self.user.addresses.get(is_default=True), b)
        self.client.post(f"/accounts/addresses/{b.pk}/delete/")
        self.assertEqual(self.user.addresses.get(is_default=True), a)

    def test_get_khong_duoc_xoa_hay_dat_mac_dinh(self):
        a = services.create_address(self.user, **ADDR)
        self.assertEqual(self.client.get(f"/accounts/addresses/{a.pk}/delete/").status_code, 405)
        self.assertEqual(self.client.get(f"/accounts/addresses/{a.pk}/default/").status_code, 405)
        self.assertTrue(Address.objects.filter(pk=a.pk).exists())

    def test_khong_truy_cap_duoc_dia_chi_cua_nguoi_khac(self):
        pk = self.theirs.pk
        self.assertEqual(self.client.get(f"/accounts/addresses/{pk}/edit/").status_code, 404)
        self.assertEqual(
            self.client.post(f"/accounts/addresses/{pk}/edit/", dict(ADDR, street="hack")).status_code, 404
        )
        self.assertEqual(self.client.post(f"/accounts/addresses/{pk}/delete/").status_code, 404)
        self.assertEqual(self.client.post(f"/accounts/addresses/{pk}/default/").status_code, 404)
        self.theirs.refresh_from_db()
        self.assertEqual(self.theirs.street, "12 Lê Lợi")

    def test_danh_sach_chi_hien_dia_chi_cua_minh_va_escape_html(self):
        services.create_address(self.user, **dict(ADDR, receiver="<script>x</script>"))
        resp = self.client.get("/accounts/addresses/")
        self.assertContains(resp, "&lt;script&gt;x&lt;/script&gt;")
        self.assertNotContains(resp, "<script>x</script>")
        self.assertEqual(len(resp.context["addresses"]), 1)

    def test_danh_sach_trong(self):
        self.assertContains(self.client.get("/accounts/addresses/"), "Bạn chưa có địa chỉ nào")