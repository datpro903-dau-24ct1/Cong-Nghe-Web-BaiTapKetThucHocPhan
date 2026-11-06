from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("dat-hang/", views.checkout_view, name="checkout"),
    path("dat-hang/thanh-cong/<int:order_id>/", views.order_success_view, name="success"),
    path("don-hang/", views.order_list_view, name="list"),
    path("don-hang/<int:order_id>/", views.order_detail_view, name="detail"),
    path("don-hang/<int:order_id>/huy/", views.order_cancel_view, name="cancel"),
    path("thong-ke/", views.dashboard_view, name="dashboard"),
]
