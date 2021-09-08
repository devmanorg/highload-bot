import os
import time
import rollbar
import textwrap
import phonenumbers
import telegram.ext

from django.utils.timezone import now

from telegram import ReplyKeyboardMarkup

from telegram.ext import (
    CallbackQueryHandler,
    PollAnswerHandler,
    CommandHandler,
    Filters,
    MessageHandler,
    Updater
    )

from .models import Player, Rebus, PollResult, RebusAttempt

from .tg_lib import (
    check_answer,
    check_draws,
    get_rest_time_to_draw,
    get_rest_time_to_end_draw,
    get_message_of_waiting_to_start_draw,
    get_message_of_waiting_to_end_draw,
    go_to_next_rebus,
    read_poll_questions,
    show_auth_keyboard,
    show_rebus_start_keyboard,
    show_poll_start_keyboard,
    show_send_contact_keyboard,
    show_rebus,
    show_hint,
    show_end_message,
    show_select_competition_keyboard,
    show_next_question,
    show_end_poll_message,
    show_message_about_draw_status
    )


rollbar.init(os.getenv('ROLLBAR_TOKEN'))

MAX_PUZZLES_TO_WIN = os.getenv('MAX_PUZZLES_TO_WIN', 10)
TYPE_COMPETITION = {'is_rebus': 'РЕБУС', 'is_poll': 'ОПРОС'}


def get_user(func):
    def wrapper(update, context):
        chat_id = update.message.chat_id
        user, _ = Player.objects.get_or_create(telegram_id=chat_id)
        context.user_data['user'] = user
        return func(update, context)
    return wrapper


class TgDialogBot(object):

    def __init__(self, tg_token, states_functions):
        self.tg_token = tg_token
        self.states_functions = states_functions
        self.updater = Updater(token=tg_token, use_context=True)
        self.updater.dispatcher.add_handler(CommandHandler('start', get_user(self.handle_users_reply)))
        self.updater.dispatcher.add_handler(CommandHandler('help', self.help_handler))
        self.updater.dispatcher.add_handler(CallbackQueryHandler(get_user(self.handle_users_reply)))
        self.updater.dispatcher.add_handler(MessageHandler(Filters.text | Filters.contact, get_user(self.handle_users_reply)))
        self.updater.dispatcher.add_handler(PollAnswerHandler(get_user(self.handle_users_reply)))
        self.updater.dispatcher.add_error_handler(self.error)
        self.job_queue = self.updater.job_queue

    def handle_users_reply(self, update, context):
        user = context.user_data['user']
        if update.message:
            user_reply = update.message.text
            chat_id = update.message.chat_id
        elif update.callback_query:
            user_reply = update.callback_query.data
            chat_id = update.callback_query.message.chat_id
        elif update.poll_answer:
            user_reply = update.poll_answer.option_ids
            chat_id = update.poll_answer.user.id
        else:
            return

        if not context.bot_data.get('job_queue'):
            context.bot_data.update({'job_queue': self.job_queue})

        if user_reply == '/start':
            user_state = 'START'
            context.user_data.update({
                'chat_id': chat_id, 'current_rebus_is_guessed': False,
                'current_rebus': '', 'successful_attempts': 0,
                'current_question': 0, 'current_competition': '',
                'poll_id': 0, 'poll_questions': ''
                })
        else:

            self.update_user_data(chat_id, context)
            user_state = user.bot_state
            user_state = user_state if user_state else 'HANDLE_AUTH'

        state_handler = self.states_functions[user_state]
        next_state = state_handler(context.bot, update, context)
        self.save_user_data(chat_id, context)
        user.bot_state = next_state
        user.save()

    def error(self, update, context):
        if isinstance(context.error, FileNotFoundError):
            handle_error_poll_not_found(context.bot, update.effective_chat.id)
        else:
            rollbar.report_exc_info()

    def help_handler(self, update, context):
        update.message.reply_text("Используйте /start для того, что бы перезапустить бот")

    def update_user_data(self, chat_id, context):
        user_data = context.user_data
        user = user_data['user']
        amount_rebus_success_attempts = RebusAttempt.objects.get_amount_rebus_seccusses_attempts(user)
        current_rebus = user.get_current_rebus()
        user_data['chat_id'] = chat_id
        user_data['current_competition'] = user.current_competition
        user_data['current_rebus_is_guessed'] = user.is_current_rebus_finished
        user_data['successful_attempts'] = amount_rebus_success_attempts
        user_data['current_rebus'] = current_rebus if current_rebus else Rebus.objects.fresh(user).next()
        user_data['current_question'] = PollResult.objects.get_current_question_by_user(user)
        user_data['poll_id'] = PollResult.objects.get_poll_id(user)
        user_data['poll_questions'] = read_poll_questions()

    def save_user_data(self, chat_id, context):
        user_data = context.user_data
        user = user_data['user']
        user.change_current_competition(user_data['current_competition'])
        user.change_current_rebus_finished(user_data['current_rebus_is_guessed'])
        PollResult.objects.save_current_question(user, user_data['current_question'])


def start(bot, update, context):
    chat_id = update.message.chat_id
    show_auth_keyboard(bot, chat_id)
    return 'HANDLE_AUTH'


def handle_auth(bot, update, context):
    user = context.user_data['user']
    if not update.message:
        return 'HANDLE_AUTH'
    chat_id = update.message.chat_id
    if update.message.contact:
        phone_number = update.message.contact.phone_number
        if phone_number and phonenumbers.is_valid_number(phonenumbers.parse(phone_number, 'RU')):
            user.phone_number = phone_number
            user.save()
            bot.send_message(
                chat_id=chat_id,
                text=f'Введите Ваше Имя и Фамилию:',
                reply_markup=telegram.ReplyKeyboardRemove()
                )
            return 'HANDLE_AUTH'
        else:
            bot.send_message(
                chat_id=chat_id,
                text='Вы ввели неверный номер телефона. Попробуйте еще раз:'
                )
            return 'HANDLE_AUTH'
    elif update.message.text:
        if 'Авторизоваться' in update.message.text:
            show_send_contact_keyboard(bot, chat_id)
            bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)
            return 'HANDLE_AUTH'
        else:
            user.full_name = update.message.text
            user.save()
            show_select_competition_keyboard(bot, update.message.chat_id, 'Выберите конкурс:')
            return 'HANDLE_SELECTIONS'


def handle_select(bot, update, context):
    if not update.message or not update.message.text:
        return 'HANDLE_SELECTIONS'
    user_data = context.user_data
    user = user_data['user']
    chat_id = update.message.chat_id
    draws = check_draws(TYPE_COMPETITION['is_rebus'])
    if 'Выиграть футболку' in update.message.text:
        user_data['current_competition'] = TYPE_COMPETITION['is_poll']
        show_poll_start_keyboard(bot, chat_id, user.is_finished_poll())
        return 'HANDLE_POLL'
    if 'Выиграть рюкзак/сумку' in update.message.text:
        user_data['current_competition'] = TYPE_COMPETITION['is_rebus']
        draws = check_draws(user_data['current_competition'])
        rest_time_to_draw = get_rest_time_to_draw(draws)
        if draws and not rest_time_to_draw:
            show_rebus_start_keyboard(bot, chat_id, context, MAX_PUZZLES_TO_WIN)
            return 'HANDLE_REBUS'
        elif draws and rest_time_to_draw:
            start_jobs(
                chat_id, send_message_for_start_draw, context, once=True,
                start_at=draws.start_at, name='send_message_for_start_draw'
                )
            rest_hours_to_draw, rest_minutes_to_draw = rest_time_to_draw
            show_select_competition_keyboard(
                bot, chat_id,
                get_message_of_waiting_to_start_draw(rest_hours_to_draw, rest_minutes_to_draw)
                )
        else:
            show_select_competition_keyboard(
                bot, chat_id,
                'Активные конкурсы отсутствуют. Пока Вы можете выйграть 👕 футболку.'
            )
    return 'HANDLE_SELECTIONS'


def handle_end_competition(bot, chat_id, context):
    context.user_data.update({
        'current_rebus_is_guessed': False, 'current_rebus': None,
        'current_question': 0, 'current_competition': '', 'poll_id': 0
    })
    show_select_competition_keyboard(bot, chat_id, 'Выберите конкурс:')
    return 'HANDLE_SELECTIONS'


def handle_rebus(bot, update, context):
    user_data = context.user_data
    if not update.message or not update.message.text:
        return 'HANDLE_REBUS'
    chat_id = update.message.chat_id
    if 'Игра закончена' in update.message.text:
        return handle_end_competition(bot, chat_id, context)
    elif 'Закончить игру' in update.message.text:
        successful_attempts = user_data['successful_attempts']
        message = textwrap.dedent(f'''
            Спасибо за участие в игре 👏
            Вы угадали {successful_attempts} из {MAX_PUZZLES_TO_WIN} ребусов''')
        return finish_rebus(bot, chat_id, context, message)
    elif update.message.text == 'Начать игру' or\
            'Продолжить игру' in update.message.text:
        return start_rebus(bot, chat_id, context)
    elif 'Продолжить (' in update.message.text:
        return go_next_rebus(bot, chat_id, context)
    elif 'Получить подсказку' in update.message.text:
        show_hint(bot, chat_id, user_data['current_rebus'])
        return 'HANDLE_REBUS'
    else:
        return handle_answers(bot, chat_id, update.message.text, context)


def start_rebus(bot, chat_id, context):
    user_data = context.user_data
    user = user_data['user']
    current_rebus = user_data['current_rebus']
    if current_rebus and user_data['successful_attempts'] < int(MAX_PUZZLES_TO_WIN):
        start_jobs(chat_id, show_rebus_reminder, context, name='show_rebus_reminder')
        user_data['current_rebus_is_guessed'] = False
        help_message = 'ℹ️ Отгадайте и введите слово на картинке. Если затрудняетесь, нажмите "Получить подсказку" ℹ️'
        show_rebus(bot, chat_id, current_rebus, help_message)
        user.change_current_rebus(current_rebus.id)
        return 'HANDLE_REBUS'
    elif current_rebus and user_data['successful_attempts'] == int(MAX_PUZZLES_TO_WIN):
        show_message_about_draw_status(bot, chat_id)
        return handle_end_competition(bot, chat_id, context)
    else:
        handle_error_rebus_not_found(bot, chat_id)
        return handle_end_competition(bot, chat_id, context)


def go_next_rebus(bot, chat_id, context):
    user_data = context.user_data
    user = user_data['user']
    if user_data['successful_attempts'] == int(MAX_PUZZLES_TO_WIN):
        message = textwrap.dedent('''
            Поздравляем. Подойдите на стенд ⬛⬛⬛⬛⬛, покажите данное сообщение и примите
            участие в розыгрыше рюкзака/сумки 🎁''')
        return finish_rebus(bot, chat_id, context, message)
    elif user_data['successful_attempts'] == Rebus.objects.count():
        message = textwrap.dedent(f'''
            Отсутствуют доступные ребусы.
            Спасибо за участие в игре 👏
            Вы угадали {user_data['successful_attempts']} из {MAX_PUZZLES_TO_WIN} ребусов''')
        return finish_rebus(bot, chat_id, context, message)
    else:
        user_data['current_rebus'] = Rebus.objects.fresh(user).next()
        show_rebus(bot, chat_id, user_data['current_rebus'])
        user.change_current_rebus(user_data['current_rebus'].id)
    return 'HANDLE_REBUS'


def finish_rebus(bot, chat_id, context, text_message):
    show_end_message(bot, chat_id, text_message)
    stop_jobs(chat_id, context, name='show_rebus_reminder')
    return handle_end_competition(bot, chat_id, context)


def handle_answers(bot, chat_id, answer, context):
    user_data = context.user_data
    if user_data['current_competition'] == TYPE_COMPETITION['is_rebus']:
        return handle_rebus_answer(bot, chat_id, answer, context)
    if user_data['current_competition'] == TYPE_COMPETITION['is_poll']:
        return handle_poll_answer(bot, chat_id, answer, context)


def handle_poll(bot, update, context):
    if update.message and update.message.text:
        return handle_poll_messages(bot, update, context)

    if update.poll_answer and update.poll_answer.option_ids:
        return handle_poll_answers(bot, update, context)


def handle_rebus_answer(bot, chat_id, answer, context):
    user_data = context.user_data
    user = user_data['user']
    if user_data['successful_attempts'] == int(MAX_PUZZLES_TO_WIN):
        message = textwrap.dedent('''
            Поздравляем. Подойдите на стенд ⬛⬛⬛⬛⬛, покажите данное сообщение и примите
            участие в розыгрыше рюкзака/сумки 🎁''')
        return finish_rebus(bot, chat_id, context, message)
    if check_answer(chat_id, answer, context):
        user_data['current_rebus_is_guessed'] = True
        Rebus.objects.add_attempt(user_data['current_rebus'].id, user, answer, True, now())
        go_to_next_rebus(bot, chat_id, 'Верный ответ. Продолжим?', context, MAX_PUZZLES_TO_WIN)
        return 'HANDLE_REBUS'
    elif not user_data['current_rebus_is_guessed']:
        Rebus.objects.add_attempt(user_data['current_rebus'].id, user, answer, False, now())
        bot.send_message(
            chat_id=chat_id,
            text='Ответ не верный. Попробуйте еще раз.',
            reply_markup=ReplyKeyboardMarkup(
                [['❓ Получить подсказку'], ['✖ Закончить игру']],
                one_time_keyboard=False, row_width=1, resize_keyboard=True
            )
        )
        return 'HANDLE_REBUS'
    else:
        return 'HANDLE_REBUS'


def handle_poll_answer(bot, chat_id, answer, context):
    user_data = context.user_data
    question_number = user_data['current_question']
    message = user_data['poll_questions'][question_number - 1]
    PollResult.objects.add_question_answer_pair(
        user_data['poll_id'],
        question_number, message['question'],
        answer, now()
    )
    next_question = [item['next_question'] for item in message['answer options'] if item['value'] == answer]
    if next_question:
        return next_question[0]


def handle_poll_messages(bot, update, context):
    user_data = context.user_data
    user = user_data['user']
    chat_id = update.message.chat_id
    question_number = user_data['current_question']

    if update.message.text == 'Опрос' or\
            update.message.text == 'Пройти опрос заново':
        show_next_question(bot, chat_id, question_number, context)
        user_data['current_question'] = question_number + 1
        return 'HANDLE_POLL'

    if 'Завершить опрос' in update.message.text or\
            'Отказаться от опроса' in update.message.text:
        PollResult.objects.del_unfinished_poll(user)
        return handle_end_competition(bot, chat_id, context)

    current_question_number = handle_answers(bot, chat_id, update.message.text, context)
    question_number = current_question_number if current_question_number else question_number

    if question_number == len(user_data['poll_questions']):
        show_end_poll_message(bot, chat_id)
        PollResult.objects.finish_poll(user, question_number, True)
        return handle_end_competition(bot, chat_id, context)

    else:
        show_next_question(bot, chat_id, question_number, context)
        user_data['current_question'] = question_number + 1
        return 'HANDLE_POLL'


def handle_poll_answers(bot, update, context):
    user_data = context.user_data
    chat_id = update.poll_answer.user.id
    question_number = user_data['current_question']
    current_message = user_data['poll_questions'][question_number - 1]
    answers = [item for id, item in enumerate(current_message['poll options']) if id in update.poll_answer.option_ids]
    if answers:
        question_number = sorted(answers, key=lambda x: x['next_question'])[0]['next_question']
        string_answers = ' | '.join([item['value'] for item in answers])
        PollResult.objects.add_question_answer_pair(
            user_data['poll_id'],
            question_number, current_message['question'],
            string_answers, now()
        )
    else:
        question_number, string_answers = question_number + 1, ''
    show_next_question(bot, chat_id, question_number, context)
    user_data['current_question'] = question_number + 1
    return 'HANDLE_POLL'


def handle_error_poll_not_found(bot, chat_id):
    message = bot.send_message(chat_id=chat_id, text=f'🚫 Не обнаружен файл с опросами или картинка ребуса!')
    time.sleep(10)
    bot.delete_message(chat_id=chat_id, message_id=message.message_id)
    user = Player.objects.get(telegram_id=chat_id)
    user.bot_state = 'HANDLE_SELECTIONS'
    user.save()


def handle_error_rebus_not_found(bot, chat_id):
    message = bot.send_message(chat_id=chat_id, text=f'🚫 Отсутствуют доступные ребусы!')
    time.sleep(10)
    bot.delete_message(chat_id=chat_id, message_id=message.message_id)


def start_jobs(chat_id, job, context, once=False, **kwargs):
    user_data = context.user_data
    job_name = f'{chat_id}_{kwargs["name"]}'
    if not context.bot_data['job_queue'].get_jobs_by_name(job_name):
        if once:
            context.bot_data['job_queue'].run_once(
                job, when=kwargs['start_at'],
                name=job_name, context=user_data
            )
        else:
            context.bot_data['job_queue'].run_repeating(
                job, interval=60, first=0,
                name=job_name, context=user_data
            )


def stop_jobs(chat_id, context, **kwargs):
    job_name = f'{chat_id}_{kwargs["name"]}'
    found_job = context.bot_data['job_queue'].get_jobs_by_name(job_name)
    found_job[0].schedule_removal() if found_job else True


def show_rebus_reminder(context):
    chat_id = context.job.context['chat_id']
    draws = check_draws(TYPE_COMPETITION['is_rebus'])
    rest_time_to_end_draw = get_rest_time_to_end_draw(draws)
    if draws and rest_time_to_end_draw:
        rest_hours_to_draw, rest_minutes_to_draw = rest_time_to_end_draw
        if not rest_hours_to_draw and rest_minutes_to_draw <= 5:
            context.bot.send_message(
                chat_id=chat_id,
                text=get_message_of_waiting_to_end_draw(rest_hours_to_draw, rest_minutes_to_draw)
            )
    if not rest_time_to_end_draw:
        successful_attempts = context.job.context['successful_attempts']
        message = textwrap.dedent(f'''
            Спасибо за участие в игре 👏
            Вы угадали {successful_attempts} из {MAX_PUZZLES_TO_WIN} ребусов''')
        show_end_message(context.bot, chat_id, message, remove_keyboard=False)
        context.job.schedule_removal()


def send_message_for_start_draw(context):
    chat_id = context.job.context['chat_id']
    draws = check_draws(TYPE_COMPETITION['is_rebus'])
    rest_time_to_draw = get_rest_time_to_draw(draws)
    if draws and not rest_time_to_draw:
        context.bot.send_message(
            chat_id=chat_id,
            text=f'👌 Розыгрыш рюкзака/сумки начался. Вы можете принять участие.'
        ) if context.job.context['current_competition'] == TYPE_COMPETITION['is_rebus'] else True
        context.job.schedule_removal()
