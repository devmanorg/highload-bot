from django.contrib import admin
from django.conf import settings
from django.urls import path, include
from django.conf.urls.static import static

from telegram_bot.views import redirect2admin


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', redirect2admin),
    path('', include('telegram_bot.urls'))
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        path('__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns
