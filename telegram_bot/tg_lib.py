import re
import json
import textwrap
from os import path #FIXME Временное решения

import telegram.ext
import requests

from telegram import (
    ReplyKeyboardMarkup,
    KeyboardButton
)

from django.utils.timezone import now

from .models import Draw, Rebus


TYPE_COMPETITION = {'is_rebus': 'РЕБУС', 'is_poll': 'ОПРОС'}


def check_answer(chat_id, answer, context):
    rebus = Rebus.objects.get(pk=context.user_data['current_rebus'].id)
    answers = rebus.answers.all()
    regex_object = re.compile(r'[\n+|\r|\(|\)|\.|\,|\:|\;|\"|\[|\]|\s]')
    answer_seq = [word for word in regex_object.split(answer.upper()) if len(word) > 2]
    correct_answer_seq = [word for word in [item.answer.upper() for item in answers] if len(word) > 2]
    return len(answer_seq) == len(set(answer_seq) & set(correct_answer_seq)) and len(answer_seq) > 0


def show_rebus_start_keyboard(bot, chat_id, context, max_puzzles):
    user_data = context.user_data
    if user_data['successful_attempts'] and user_data['successful_attempts'] < int(max_puzzles):
        message = f'Вы уже отгадали {user_data["successful_attempts"]} ребусов. Продолжите игру и получите подарок.'
        keyboard = KeyboardButton(text="Продолжить игру")
    elif user_data['successful_attempts'] and user_data['successful_attempts'] == int(max_puzzles):
        message = f'Вы уже учавствуете в розыгрыше рюкзака/сумки. Подойдите на стенд ⬛⬛⬛⬛⬛.'
        keyboard = KeyboardButton(text="✖ Закончить игру")
    else:
        message = 'Разгадайте ребусы и получите подарок.'
        keyboard = KeyboardButton(text="Начать игру")
    return bot.send_message(
        chat_id=chat_id, text=message,
        reply_markup=ReplyKeyboardMarkup(
            [[keyboard]], one_time_keyboard=False,
            row_width=1, resize_keyboard=True
        )
    )


def show_poll_start_keyboard(bot, chat_id, finished_poll):
    if finished_poll:
        message = textwrap.dedent('''
            Вы уже прошли опрос. Хотите повторить? Вторую футболку 👕 за это не дают.''')
        keyboard = [["Пройти опрос заново"], ["Отказаться от опроса"]]
    else:
        message = textwrap.dedent('''
            Чтобы получить 👕 футболку, нужно пройти небольшой опрос.
            После прохождения подойти на стенд ⬛⬛⬛⬛⬛ и показать сообщение о прохождении опроса.''')
        keyboard = [["Опрос"]]
    return bot.send_message(
        chat_id=chat_id, text=message,
        reply_markup=ReplyKeyboardMarkup(
            keyboard, one_time_keyboard=False,
            row_width=1, resize_keyboard=True
        )
    )


def show_rebus(bot, chat_id, current_rebus, description=''):
    reply_markup = ReplyKeyboardMarkup(
        [['❓ Получить подсказку'], ['✖ Закончить игру']],
        one_time_keyboard=False, row_width=1, resize_keyboard=True
    )
    
    if requests.get(current_rebus.image.url).ok:
        # for production server
        bot.send_photo(
            chat_id=chat_id, photo=image.url, reply_markup=reply_markup,
            caption=' '.join([item for item in (current_rebus.text, description) if item])
        )
    else:
        # for localhost
        with open(current_rebus.image.path, 'rb') as image:
            bot.send_photo(
                chat_id=chat_id, photo=image, reply_markup=reply_markup,
                caption=' '.join([item for item in (current_rebus.text, description) if item])
            )


def show_hint(bot, chat_id, current_rebus, description=''):
    reply_markup = ReplyKeyboardMarkup(
        [['❓ Получить подсказку'], ['✖ Закончить игру']],
        one_time_keyboard=False, row_width=1, resize_keyboard=True
    )
    if current_rebus.hint:
        bot.send_message(chat_id=chat_id, text=current_rebus.hint, reply_markup=reply_markup)
    else:
        bot.send_message(chat_id=chat_id, text='Подсказка отсутствует', reply_markup=reply_markup)


def go_to_next_rebus(bot, chat_id, description, context, max_puzzles):
    user_data = context.user_data
    successful_attempts = user_data["successful_attempts"] + 1
    reply_markup = ReplyKeyboardMarkup(
        [
            [f'✅ Продолжить ({successful_attempts} из {max_puzzles} успешно)'],
            ['✖ Закончить игру']
        ],
        one_time_keyboard=False, row_width=1, resize_keyboard=True
    )
    bot.send_message(chat_id=chat_id, text=description, reply_markup=reply_markup)


def show_end_message(bot, chat_id, text_message, remove_keyboard=True):
    if remove_keyboard:
        bot.send_message(chat_id=chat_id, text=text_message)
    else:
        bot.send_message(
            chat_id=chat_id, text=text_message,
            reply_markup=ReplyKeyboardMarkup(
                [['Игра закончена']], one_time_keyboard=False,
                row_width=1, resize_keyboard=True
            )
        )


def show_message_about_draw_status(bot, chat_id):
    bot.send_message(
        chat_id=chat_id,
        text='🎁 Вы уже участвуете в конкурсе. ⏰ Дождитесь результатов розыгрыша на стенде ⬛⬛⬛⬛⬛'
    )


def delete_messages(bot, chat_id, message_id, message_numbers=1):
    if not message_id:
        return
    for offset_id in range(message_numbers):
        bot.delete_message(chat_id=chat_id, message_id=int(message_id) - offset_id)


def show_auth_keyboard(bot, chat_id):
    message = textwrap.dedent('''
        Перед началом использования необходимо отправить номер телефона.
        Пожалуйста, нажмите на кнопку Авторизоваться ниже:''')
    auth_keyboard = KeyboardButton(text="🔐 Авторизоваться")
    reply_markup = ReplyKeyboardMarkup(
        [[auth_keyboard]], one_time_keyboard=False,
        row_width=1, resize_keyboard=True
    )
    bot.send_message(chat_id=chat_id, text=message, reply_markup=reply_markup)


def show_send_contact_keyboard(bot, chat_id):
    message = '''Продолжая регистрацию вы соглашаетесь с политикой конфиденциальности'''
    contact_keyboard = KeyboardButton(text="☎ Передать контакт", request_contact=True)
    reply_markup = ReplyKeyboardMarkup(
        [[contact_keyboard]], one_time_keyboard=False,
        row_width=1, resize_keyboard=True
    )
    bot.send_message(chat_id=chat_id, text=message, reply_markup=reply_markup)


def show_auth_end_keyboard(bot, chat_id):
    message = '''Благодарим Вас за авторизацию'''
    auth_end_keyboard = KeyboardButton(text="Продолжить")
    reply_markup = ReplyKeyboardMarkup(
        [[auth_end_keyboard]], one_time_keyboard=False,
        row_width=1, resize_keyboard=True
    )
    bot.send_message(chat_id=chat_id, text=message, reply_markup=reply_markup)


def show_select_competition_keyboard(bot, chat_id, text_message):
    reply_markup = ReplyKeyboardMarkup(
        [['Выиграть футболку 👕'], ['Выиграть рюкзак/сумку 🎒']],
        one_time_keyboard=False, row_width=1, resize_keyboard=True
    )
    return bot.send_message(chat_id=chat_id, text=text_message, reply_markup=reply_markup)


def show_next_question(bot, chat_id, question_number, context):
    user_data = context.user_data
    questions = user_data['poll_questions']
    message = questions[question_number]
    answer_options = message['answer options']
    poll_options = message['poll options']
    reply_markup = ReplyKeyboardMarkup(
        [['✖ Завершить опрос']],
        one_time_keyboard=False, row_width=1,
        resize_keyboard=True
    )
    if poll_options:
        message = bot.send_poll(
            chat_id, message['question'],
            [item['value'] for item in poll_options],
            is_anonymous=False, allows_multiple_answers=True,
            reply_markup=reply_markup
        )
    elif answer_options:
        reply_markup = ReplyKeyboardMarkup(
            [[item['value'] for item in answer_options]],
            one_time_keyboard=False, row_width=1,
            resize_keyboard=True
        )
        bot.send_message(chat_id=chat_id, text=message['question'], reply_markup=reply_markup)
    else:
        bot.send_message(chat_id=chat_id, text=message['question'], reply_markup=reply_markup)


def show_end_poll_message(bot, chat_id):
    message = textwrap.dedent('''
        Спасибо за пройденный опрос. Подойдите на стенд ⬛⬛⬛⬛⬛, покажите данное сообщение и получите футболку 👕''')
    bot.send_message(chat_id=chat_id, text=message, reply_markup=telegram.ReplyKeyboardRemove())


def read_poll_questions():
    with open('questions_to_clients.txt', 'r') as file_handler:
        poll_questions = json.load(file_handler)
    return poll_questions


def check_draws(current_competition):
    if current_competition == TYPE_COMPETITION['is_rebus']:
        return Draw.objects.get_draw()


def get_rest_time_to_draw(draw):
    if draw and now() < draw.start_at:
        return divmod(divmod((draw.start_at - now()).seconds, 60)[0], 60)


def get_rest_time_to_end_draw(draw):
    if draw and draw.start_at < now() < draw.end_at:
        return divmod(divmod((draw.end_at - now()).seconds, 60)[0], 60)


def get_message_of_waiting_to_start_draw(rest_hours, rest_minutes):
    if rest_hours == 0 and rest_minutes == 0:
        return textwrap.dedent(f'''
            ⏰ До начала розыгрыша осталось менее одной минуты.''')
    else:
        agree_with_hours = make_agree_with_number(rest_minutes, 'час', 'часа', 'часов')
        agree_with_minutes = make_agree_with_number(rest_minutes, 'минута', 'минуты', 'минут')
        return textwrap.dedent(f'''
            ⏰ До начала розыгрыша осталось {rest_hours} {agree_with_hours} {rest_minutes} {agree_with_minutes}.''')


def get_message_of_waiting_to_end_draw(rest_hours, rest_minutes):
    if rest_hours == 0 and rest_minutes == 0:
        return textwrap.dedent(f'''
            ⏰ До окончания розыгрыша осталось менее одной минуты.''')
    else:
        agree_with_minutes = make_agree_with_number(rest_minutes, 'минута', 'минуты', 'минут')
        return textwrap.dedent(f'''
            ⏰ До окончания розыгрыша осталось {rest_minutes} {agree_with_minutes}.''')


def make_agree_with_number(number, form1, form2, form5):
    if number is None:
        return form5

    normalized_number = abs(number) % 100
    last_digit = normalized_number % 10
    if 10 < normalized_number < 20:
        return form5
    if 1 < last_digit < 5:
        return form2
    if last_digit == 1:
        return form1
    return form5
