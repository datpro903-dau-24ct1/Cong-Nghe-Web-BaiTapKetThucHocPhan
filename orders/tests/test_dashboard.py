from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from catalog import services as catalog_services
from orders import selectors
from orders.models import Order, OrderItem


class DashboardBaseTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tz = ZoneInfo("Asia/Ho_Chi_Minh")
        cls.category = catalog_services.create_category("Scale Figure")
        cls.series = catalog_services.create_series("One Piece")
        cls.brand = catalog_services.create_brand("Good Smile Company")
        cls.p1 = catalog_services.create_product(
            name="Luffy Gear 5",
            category=cls.category,
            series=cls.series,
            brand=cls.brand,
            price=Decimal(1000000),
            stock=20,
        )
        cls.p2 = catalog_services.create_product(
            name="Zoro Enma",
            category=cls.category,
            series=cls.series,
            brand=cls.brand,
            price=Decimal(1500000),
            stock=20,
        )
        cls.customer = User.objects.create_user(
            email="customer@example.com",
            password="Password123!",
            full_name="Khách Hàng",
        )
        cls.staff = User.objects.create_user(
            email="staff@example.com",
            password="Password123!",
            full_name="Nhân Viên",
            is_staff=True,
        )

    def create_order_at(
        self,
        *,
        created_at,
        status=Order.Status.COMPLETED,
        items=None,
        shipping_fee=Decimal(30000),
    ):
        items = items or [(self.p1, 1, self.p1.price)]
        subtotal = sum(qty * price for _, qty, price in items)
        total = subtotal + shipping_fee
        order = Order.objects.create(
            user=self.customer,
            receiver="Khách Hàng",
            phone="0901234567",
            street="123 Lê Lợi",
            ward="Phường Bến Nghé",
            district="Quận 1",
            province="TP. Hồ Chí Minh",
            status=status,
            subtotal=subtotal,
            shipping_fee=shipping_fee,
            total=total,
        )
        Order.objects.filter(pk=order.pk).update(created_at=created_at)
        order.created_at = created_at
        for product, qty, unit_price in items:
            OrderItem.objects.create(
                order=order,
                product=product,
                product_name=product.name,
                unit_price=unit_price,
                quantity=qty,
            )
        return order


class DashboardSelectorTests(DashboardBaseTestCase):
    def test_khong_co_du_lieu_tra_ve_0_va_danh_sach_rong(self):
        stats = selectors.get_dashboard_stats()
        self.assertEqual(stats["total_revenue"], Decimal(0))
        self.assertEqual(stats["total_orders"], 0)
        self.assertEqual(stats["completed_orders"], 0)
        self.assertEqual(stats["cancelled_orders"], 0)
        self.assertEqual(stats["top_products"], [])
        self.assertEqual(stats["daily_orders"], [])

    def test_tinh_doanh_thu_top_san_pham_va_don_theo_ngay(self):
        dt1 = datetime(2026, 11, 5, 10, 0, tzinfo=self.tz)
        dt2 = datetime(2026, 11, 6, 14, 0, tzinfo=self.tz)

        # Đơn 1 (Hoàn tất): 2 x p1 (2.000.000) + 1 x p2 (1.500.000) + ship 30.000 = 3.530.000
        self.create_order_at(
            created_at=dt1,
            status=Order.Status.COMPLETED,
            items=[
                (self.p1, 2, Decimal(1000000)),
                (self.p2, 1, Decimal(1500000)),
            ],
        )
        # Đơn 2 (Hoàn tất): 3 x p2 (4.500.000) + ship 30.000 = 4.530.000
        self.create_order_at(
            created_at=dt2,
            status=Order.Status.COMPLETED,
            items=[(self.p2, 3, Decimal(1500000))],
        )
        # Đơn 3 (Đã hủy): không được cộng vào doanh thu hoàn tất hay top sản phẩm
        self.create_order_at(
            created_at=dt2,
            status=Order.Status.CANCELLED,
            items=[(self.p1, 10, Decimal(1000000))],
        )

        stats = selectors.get_dashboard_stats()
        self.assertEqual(stats["total_orders"], 3)
        self.assertEqual(stats["completed_orders"], 2)
        self.assertEqual(stats["cancelled_orders"], 1)
        self.assertEqual(stats["total_revenue"], Decimal(8060000))

        # Top sản phẩm: p2 bán 4 cái (6.000.000) xếp trên p1 bán 2 cái (2.000.000)
        top = stats["top_products"]
        self.assertEqual(len(top), 2)
        self.assertEqual(top[0]["product_name"], "Zoro Enma")
        self.assertEqual(top[0]["total_quantity"], 4)
        self.assertEqual(top[0]["total_amount"], Decimal(6000000))
        self.assertEqual(top[1]["product_name"], "Luffy Gear 5")
        self.assertEqual(top[1]["total_quantity"], 2)
        self.assertEqual(top[1]["total_amount"], Decimal(2000000))

        # Đơn theo ngày: 05/11 (1 đơn, 1 hoàn tất, 3.530.000) và 06/11 (2 đơn, 1 hoàn tất, 4.530.000)
        daily = stats["daily_orders"]
        self.assertEqual(len(daily), 2)
        self.assertEqual(daily[0]["date"], date(2026, 11, 5))
        self.assertEqual(daily[0]["order_count"], 1)
        self.assertEqual(daily[0]["revenue"], Decimal(3530000))
        self.assertEqual(daily[1]["date"], date(2026, 11, 6))
        self.assertEqual(daily[1]["order_count"], 2)
        self.assertEqual(daily[1]["revenue"], Decimal(4530000))

    def test_bien_mui_gio_asia_ho_chi_minh(self):
        # 00:30 ngày 05/11 giờ VN (tức 17:30 ngày 04/11 giờ UTC)
        early_vn = datetime(2026, 11, 5, 0, 30, tzinfo=self.tz)
        # 23:30 ngày 05/11 giờ VN (tức 16:30 ngày 05/11 giờ UTC)
        late_vn = datetime(2026, 11, 5, 23, 30, tzinfo=self.tz)

        self.create_order_at(created_at=early_vn, status=Order.Status.COMPLETED)
        self.create_order_at(created_at=late_vn, status=Order.Status.COMPLETED)

        # Lọc ngày 04/11 theo giờ VN -> không có đơn nào
        stats_day4 = selectors.get_dashboard_stats(
            start_date="2026-11-04", end_date="2026-11-04"
        )
        self.assertEqual(stats_day4["total_orders"], 0)
        self.assertEqual(stats_day4["daily_orders"], [])

        # Lọc ngày 05/11 theo giờ VN -> có đủ cả 2 đơn và cùng gom vào ngày 2026-11-05
        stats_day5 = selectors.get_dashboard_stats(
            start_date="2026-11-05", end_date="2026-11-05"
        )
        self.assertEqual(stats_day5["total_orders"], 2)
        self.assertEqual(len(stats_day5["daily_orders"]), 1)
        self.assertEqual(stats_day5["daily_orders"][0]["date"], date(2026, 11, 5))
        self.assertEqual(stats_day5["daily_orders"][0]["order_count"], 2)

    def test_khoang_ngay_khong_hop_le_bao_loi(self):
        with self.assertRaises(ValidationError) as ctx:
            selectors.get_dashboard_stats(
                start_date="2026-11-10", end_date="2026-11-05"
            )
        self.assertEqual(ctx.exception.code, "invalid_date_range")

        for bad_date in ("2026-13-40", "not-a-date", "05/11/2026"):
            with self.assertRaises(ValidationError) as ctx2:
                selectors.get_dashboard_stats(start_date=bad_date)
            self.assertEqual(ctx2.exception.code, "invalid_date")


class DashboardViewTests(DashboardBaseTestCase):
    def test_phan_quyen_chi_nhan_vien_va_admin_xem_duoc_dashboard(self):
        url = reverse("orders:dashboard")

        # Khách ẩn danh -> redirect login
        resp_anon = self.client.get(url)
        self.assertEqual(resp_anon.status_code, 302)

        # Khách hàng thường -> 403 Forbidden
        self.client.force_login(self.customer)
        resp_customer = self.client.get(url)
        self.assertEqual(resp_customer.status_code, 403)

        # Nhân viên -> 200 OK
        self.client.force_login(self.staff)
        resp_staff = self.client.get(url)
        self.assertEqual(resp_staff.status_code, 200)
        self.assertContains(resp_staff, "Dashboard thống kê")

    def test_dashboard_view_hien_thi_thong_bao_khi_khoang_ngay_sai(self):
        self.client.force_login(self.staff)
        url = reverse("orders:dashboard")
        resp = self.client.get(
            url, {"start_date": "2026-11-10", "end_date": "2026-11-01"}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(
            resp, "Ngày bắt đầu không được lớn hơn ngày kết thúc."
        )
