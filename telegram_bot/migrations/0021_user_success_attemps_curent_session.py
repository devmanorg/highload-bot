# Generated by Django 3.1.2 on 2020-11-12 16:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('telegram_bot', '0020_user_current_rebus'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='success_attemps_curent_session',
            field=models.IntegerField(default=0, verbose_name='Количество успешных попыток в текущий сессии'),
        ),
    ]
