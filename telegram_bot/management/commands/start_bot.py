import rollbar
from django.conf import settings
from django.core.management import BaseCommand

from telegram_bot.tg_rebus import (
    TgDialogBot,
    start,
    handle_auth,
    handle_poll,
    handle_rebus,
    handle_select
)


class Command(BaseCommand):
    def handle(self, *args, **options):
        try:
            start_bot()
        except Exception as exc:
            rollbar.report_exc_info()
            raise


def start_bot():

    bot = TgDialogBot(
        settings.TELEGRAM_ACCESS_TOKEN,
        {
            'START': start,
            'HANDLE_AUTH': handle_auth,
            'HANDLE_SELECTIONS': handle_select,
            'HANDLE_POLL': handle_poll,
            'HANDLE_REBUS': handle_rebus
        }
    )
    bot.updater.start_polling()
    bot.updater.idle()  # required in detached mode on server
