# Highload Bot

Техническое задание читать [здесь](https://gist.github.com/dvmn-tasks/7e002681fd9dc0f0da5c1907b240c053).

Сценарии использования админки [здесь](https://gist.github.com/dvmn-tasks/3555fc35ba12929d564a708fa6374208).

## Переменные окружения

Все настройки, кроме отмеченных звёздочкой `*` необязательные. На localhost в отладочном режиме сайт можно запустить почти без настроек.

\*`TELEGRAM_ACCESS_TOKEN` — токен бота;

`DEBUG` — режим отладки, по дефолту `False`

`INTERNAL_IPS` - хост для Django Debug Toolbar

`SECRET_KEY` — секретный ключ `Django`

`DATABASE_URL` — адрес базы данных. [Формат записи](https://github.com/jacobian/dj-database-url).

`ALLOWED_HOSTS` — один или несколько хостов, разделённых запятой. [Документация](https://docs.djangoproject.com/en/3.1/ref/settings/#allowed-hosts).

`ROLLBAR_TOKEN` — токен к [rollbar.com](https://rollbar.com/).

`ROLLBAR_ENVIRONMENT` — на production-сервере выставлено в `production`.

`S3_ACCESS_KEY_ID` — переключает Django на использовать S3 хранилища медиа-файлов. В названии настройки [Документация](https://django-storages.readthedocs.io/en/latest/backends/digital-ocean-spaces.html).

`S3_SECRET_ACCESS_KEY` — секретный ключ к хранилищу S3 (если используется). [Документация](https://django-storages.readthedocs.io/en/latest/backends/digital-ocean-spaces.html).

`S3_*` — множество прочих необязательных "тонких" настроек хранилища S3. См. файл settings.py.

`MAX_PUZZLES_TO_WIN` - количество ребусов, которые необходимо решить для участия в розыгрыше.

## Как установить dev-версию

Скачай репозиторий:

```sh
$ git clone https://github.com/LevelUp-developers/highload-bot.git
```

Перейжи в репозиторий, установи библиотеки и зависимости:

```sh
$ cd highload-bot
$ pip3 install -r requirements.txt
```

Накати миграцию:

```sh
$ python3 manage.py migrate
```

Запусти сервер:

```sh
$ python3 manage.py runserver
```

## Как попасть в админку

Создай нового пользователя с правами админа:

```sh
$ python3 manage.py createsuperuser
```

Запусти сервер:

```sh
$ python3 manage.py runserver
```

Перейдите по ссылке в [127.0.0.1:8000/admin](http://127.0.0.1:8000/admin).

## Как запустить Telegram-бота

Выполни команду:

```bash
$ python3 manage.py start_bot
```
