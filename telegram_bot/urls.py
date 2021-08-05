from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns
from telegram_bot.views import download_result_polls_in_csv


urlpatterns = [
    path('poll/file/', download_result_polls_in_csv)
]

urlpatterns = format_suffix_patterns(urlpatterns, allowed=['csv'])
