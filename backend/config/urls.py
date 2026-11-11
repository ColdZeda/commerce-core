"""URL 根表；业务路由按领域在各自 app 内定义后 include 进来。"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("health.urls")),
    path("api/v1/", include("accounts.urls")),
    path("api/v1/", include("catalog.urls")),
    path("api/v1/", include("promotion.urls")),
    path("api/v1/", include("trade.urls")),
]
