"""Các view xử lý trang lỗi tùy chỉnh 403, 404, 500 (CN26)."""
from django.http import HttpResponse
from django.template import loader


def error_403_view(request, exception=None):
    template = loader.get_template("403.html")
    return HttpResponse(template.render({}, request), status=403)


def error_404_view(request, exception=None):
    template = loader.get_template("404.html")
    return HttpResponse(template.render({}, request), status=404)


def error_500_view(request):
    template = loader.get_template("500.html")
    return HttpResponse(template.render({}), status=500)
