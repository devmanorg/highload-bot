from django.core.exceptions import PermissionDenied

from rollbar.contrib.django.middleware import RollbarNotifierMiddlewareExcluding404


class RollbarNotifierMiddlewareExcluding404AndPermissionDenied(RollbarNotifierMiddlewareExcluding404):
    def process_exception(self, request, exc):
        if not isinstance(exc, PermissionDenied):
            super().process_exception(request, exc)
