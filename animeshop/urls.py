from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("", include("carts.urls")),
    path("", include("orders.urls")),
    path("", include("catalog.urls")),
]

handler403 = "animeshop.views.error_403_view"
handler404 = "animeshop.views.error_404_view"
handler500 = "animeshop.views.error_500_view"

# Khi DEBUG=1, Django phục vụ ảnh tải lên (media) để xem được trên máy dev.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
