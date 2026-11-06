from django.urls import path

from . import views

urlpatterns = [
    path("", views.product_list_view, name="home"),
    path("danh-muc/<slug:slug>/", views.category_view, name="category"),
    path("san-pham/<slug:slug>/", views.product_detail_view, name="product_detail"),
    path("san-pham/<slug:slug>/danh-gia/", views.submit_review_view, name="submit_review"),
]
