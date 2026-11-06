from django.urls import path

from . import views

app_name = "carts"

urlpatterns = [
    path("gio-hang/", views.cart_view, name="cart"),
    path("gio-hang/them/<int:product_id>/", views.add_view, name="add"),
    path("gio-hang/sua/<int:product_id>/", views.update_view, name="update"),
    path("gio-hang/xoa/<int:product_id>/", views.remove_view, name="remove"),
]
