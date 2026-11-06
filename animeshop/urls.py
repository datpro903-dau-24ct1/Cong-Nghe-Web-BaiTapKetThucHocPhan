from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("", include("catalog.urls")),
]

# Khi DEBUG=1, Django phục vụ ảnh tải lên (media) để xem được trên máy dev.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)