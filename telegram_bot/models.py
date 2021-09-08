from django.utils.timezone import localtime, now
from django.db import models


class DrawQuerySet(models.QuerySet):

    def get_current_draw(self):
        return self.filter(start_at__lte=now(), end_at__gte=now())

    def get_future(self):
        future_draw = self.filter(start_at__gte=now())
        return future_draw.first() if future_draw else None

    def get_draw(self):
        draw = self.get_current_draw()
        if draw:
            return draw.first()
        return self.get_future()


class Draw(models.Model):
    title = models.CharField('Названия розыгрыша', max_length=200, unique=True)
    start_at = models.DateTimeField(
        verbose_name='Старт розыгрыша',
        default=localtime,
        db_index=True,
    )
    end_at = models.DateTimeField(
        verbose_name='Окончания розыгрыша',
        db_index=True,
    )

    objects = DrawQuerySet.as_manager()

    class Meta:
        verbose_name = 'Розыгрыш'
        verbose_name_plural = 'Розыгрыши'

    def __str__(self):
        return self.title


class Player(models.Model):
    CURRENT_COMPETITION = [
        ('РЕБУС', 'is_rebus'),
        ('ОПРОС', 'is_poll'),
    ]

    full_name = models.CharField(
        'Полное имя',
        max_length=200,
        blank=True,
    )
    phone_number = models.CharField(
        'Номер телефона',
        max_length=20,
        blank=True,
    )
    exclude_from_export = models.BooleanField(
        'Исключить из экспорта',
        default=False,
        db_index=True
    )
    created_at = models.DateTimeField(
        verbose_name='Зарегистрирован в',
        db_index=True,
        blank=True,
        null=True,
    )
    telegram_id = models.IntegerField(
        'Telegram Id',
        db_index=True,
        blank=True,
        null=True
    )
    bot_state = models.CharField(
        'Текущее состояния бота',
        max_length=100,
        blank=True,
        help_text="Стейт машина для ребуса"
    )
    current_competition = models.CharField(
        max_length=20,
        choices=CURRENT_COMPETITION,
        blank=True
    )
    gift_received = models.BooleanField('Получил подарок', default=False)
    is_current_rebus_finished = models.BooleanField(default=False)
    current_rebus = models.IntegerField(null=True, blank=True)

    class Meta:
        verbose_name = 'Участник'
        verbose_name_plural = 'Участники'

    def __str__(self):
        #  TypeError: __str__ returned non-string (type NoneType)
        return f'{self.full_name}'

    def change_current_rebus(self, current_rebus):
        self.current_rebus = current_rebus
        self.save()

    def change_current_competition(self, current_competition):
        self.current_competition = current_competition
        self.save()

    def change_current_rebus_finished(self, current_rebus_finished):
        self.is_current_rebus_finished = current_rebus_finished
        self.save()

    def is_finished_poll(self):
        is_poll = self.poll_results.filter(poll_finished=True).exists()
        return is_poll

    def get_current_rebus(self):
        rebus = Rebus.objects.filter(pk=self.current_rebus).first()
        return rebus if rebus else None


class RebusQuerySet(models.QuerySet):

    def fresh(self, user):
        return self.exclude(rebus_attempts__user=user, rebus_attempts__success=True)

    def next(self):
        return self.order_by('?').first()

    def add_attempt(self, rebus_id, user, user_answer, success, rebus_sendet_at):
        return RebusAttempt.objects.create(
            rebus=self.get(pk=rebus_id),
            user=user,
            answer=user_answer,
            success=success,
            answer_received_at=now(),
            rebus_sendet_at=rebus_sendet_at,
        )


class Rebus(models.Model):
    text = models.TextField('Описание', blank=True)
    image = models.ImageField('Изображения')
    published = models.BooleanField('Опубликовать', default=False)
    hint = models.TextField('Подсказка', blank=True)
    
    objects = RebusQuerySet.as_manager()

    class Meta:
        verbose_name = 'Ребус'
        verbose_name_plural = 'Ребусы'

    def __str__(self):
        return f'Ребус {self.id}'


class Answer(models.Model):
    rebus = models.ForeignKey(
        Rebus,
        on_delete=models.CASCADE,
        verbose_name='Ребус',
        related_name='answers',
        null=True,
    )
    answer = models.CharField('Ответ', max_length=100)

    class Meta:
        verbose_name = 'Ответ'
        verbose_name_plural = 'Ответы'

    def __str__(self):
        return f'{self.rebus}'


class RebusAttemptQuerySet(models.QuerySet):

    def get_amount_rebus_seccusses_attempts(self, user):
        amount = self.filter(success=True, user=user).count()
        return amount


class RebusAttempt(models.Model):
    rebus = models.ForeignKey(
        Rebus,
        on_delete=models.CASCADE,
        verbose_name='Ребус',
        related_name='rebus_attempts',
    )
    user = models.ForeignKey(
        Player,
        on_delete=models.CASCADE,
        verbose_name='Участник',
        related_name='user_attempts',
    )
    answer_received_at = models.DateTimeField(
        verbose_name='Ответ получен в',
        db_index=True,
        blank=True,
        null=True,
    )
    success = models.BooleanField('Успешно', default=False)
    answer = models.CharField('Ответ Юзера', max_length=100)
    rebus_sendet_at = models.DateTimeField(
        verbose_name='Ребус отправлен в',
        db_index=True,
        blank=True,
        null=True,
    )
    
    objects = RebusAttemptQuerySet.as_manager()

    class Meta:
        verbose_name = 'Попытка решить ребус'
        verbose_name_plural = 'Попытки решить ребус'

    def __str__(self):
        return f'{self.user.full_name}'


class PollResultQuerySet(models.QuerySet):
    def active_for_user(self, user):
        return self.filter(user=user, poll_finished=False).first()

    def get_current_question_by_user(self, user):
        user_poll = self.active_for_user(user)
        return user_poll.current_question if user_poll else 0

    def get_poll_id(self, user):
        user_poll = self.active_for_user(user)
        if not user_poll:
            new_poll = PollResult(
                user=user,
                started_at=now()
            )
            new_poll.save()
        return new_poll.id if not user_poll else user_poll.id

    def add_question_answer_pair(
        self, poll_id, question_slug, question, answer, asked_at,
    ):
        poll = self.get(pk=poll_id)
        question_asnwer_pair = PollQuestionAnswerPair(
            poll=poll,
            slug=question_slug,
            question=question,
            answer=answer,
            asked_at=asked_at,
            answered_at=now()
        )
        question_asnwer_pair.save()

    def save_current_question(self, user, current_question):
        user_poll = self.active_for_user(user)
        if user_poll:
            user_poll.current_question = current_question
            user_poll.save()

    def finish_poll(self, user, current_question, poll_finished):
        user_poll = self.active_for_user(user)
        if user_poll:
            user_poll.current_question = current_question
            user_poll.poll_finished = poll_finished
            user_poll.ended_at = now()
            user_poll.save()

    def del_unfinished_poll(self, user):
        user_poll = self.active_for_user(user)
        if user_poll:
            user_poll.delete()


class PollResult(models.Model):
    user = models.ForeignKey(
        Player,
        related_name='poll_results',
        verbose_name='Участник',
        on_delete=models.SET_NULL,
        null=True
    )
    current_question = models.IntegerField('Текущий вопрос', default=0)
    poll_finished = models.BooleanField('Закончил опрос', default=False)
    started_at = models.DateTimeField(
        verbose_name='Начал опрос в',
        db_index=True,
        blank=True,
        null=True,
    )
    ended_at = models.DateTimeField(
        verbose_name='Закончил опрос в',
        db_index=True,
        blank=True,
        null=True,
    )
    
    objects = PollResultQuerySet.as_manager()

    class Meta:
        verbose_name = 'Опрос'
        verbose_name_plural = 'Опросы'

    def __str__(self):
        return f'Опрос_{self.id}'


class PollQuestionAnswerPair(models.Model):
    poll = models.ForeignKey(
        PollResult,
        related_name='poll_question_answer_pairs',
        verbose_name='Опрос',
        on_delete=models.SET_NULL,
        null=True
    )
    slug = models.SlugField('Slug вопроса', null=True)
    question = models.TextField('Вопрос')
    answer = models.CharField('Ответ', max_length=200)
    asked_at = models.DateTimeField(
        verbose_name='Получил вопрос в',
        db_index=True,
        blank=True,
        null=True,
    )
    answered_at = models.DateTimeField(
        verbose_name='Ответил в',
        db_index=True,
        blank=True,
        null=True,
    )

    class Meta:
        verbose_name = 'Вопрос'
        verbose_name_plural = 'Вопросы'

    def __str__(self):
        return f'Вопрос_{self.id}'
