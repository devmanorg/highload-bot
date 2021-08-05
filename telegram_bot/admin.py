from django import forms
from django.urls import reverse
from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.timezone import now

from import_export import resources
from import_export.fields import Field
from import_export.admin import ImportExportModelAdmin

from .models import (
    Player, Draw,
    Rebus, RebusAttempt, Answer,
    PollResult, PollQuestionAnswerPair
)


class PlayerResources(resources.ModelResource):
    full_name = Field(attribute='full_name', column_name='Имя и фамилия')
    phone_number = Field(attribute='phone_number', column_name='Номер телефона')

    class Meta:
        model = Player
        fields = ('full_name', 'phone_number')

    def export(self, queryset=None, *args, **kwargs):
        queryset = queryset.filter(exclude_from_export=False)
        return super(PlayerResources, self).export(queryset, *args, **kwargs)


class DrawFilter(admin.SimpleListFilter):
    title = 'Розыгрыши'
    parameter_name = 'draw'

    def lookups(self, request, model_admin):
        return [
            ['current', 'Текущие'],
            ['future', 'Будущие'],
            ['past', 'Прошедшие'],
        ]

    def queryset(self, request, queryset):
        time = now()
        if self.value() == 'current':
            return queryset.get_current_draw()
        elif self.value() == 'future':
            return queryset.filter(start_at__gte=time)
        elif self.value() == 'past':
            return queryset.filter(end_at__lte=time)


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 0
    min_num = 1


class PollQuestionAnswerPairInline(admin.TabularInline):
    model = PollQuestionAnswerPair
    extra = 0
    readonly_fields = [
        'poll',
        'slug',
        'question',
        'answer',
        'asked_at',
        'answered_at',
    ]


@admin.register(Player)
class PlayerAdmin(ImportExportModelAdmin):
    resource_class = PlayerResources
    search_fields = ['full_name', 'telegram_id']
    list_editable = ['gift_received']
    readonly_fields = ['telegram_id', 'created_at', 'bot_state']
    list_display = [
        'full_name',
        'gift_received',
        'phone_number',
        'exclude_from_export'
    ]
    fields = [
        'full_name',
        'phone_number',
        'telegram_id',
        'created_at',
        'bot_state',
        'exclude_from_export',
    ]


class DrawForm(forms.ModelForm):

    def clean(self):
        cd = self.cleaned_data
        if cd['start_at'] >= cd['end_at']:
            self.add_error(None, 'Время окончания розыгрыша меньше или равно начало розыгрыша!')
        range_time = (cd['start_at'], cd['end_at'])
        draws = Draw.objects.filter(end_at__range=range_time)
        if draws:
            self.add_error(None, 'В данное время уже есть розыгрыш')

    class Meta:
        fields = '__all__'
        model = Draw


@admin.register(Draw)
class DrawAdmin(admin.ModelAdmin):
    form = DrawForm
    ordering = ['-end_at']
    search_fields = ['title']
    list_display = ['title',
                    'get_download_link',
                    'get_amount_users',
                    'start_at',
                    'end_at',
                    'get_status_draw',
                    ]

    def get_status_draw(self, obj):
        states_colors = {
            'текущий': 'green',
            'прошедший': 'gray',
            'будущий': 'red'
        }
        if obj.start_at <= now() <= obj.end_at:
            state = 'текущий'
        elif obj.end_at < now():
            state = 'прошедший'
        else:
            state = 'будущий'
        return mark_safe(f'<span style="color:{states_colors[state]};font-weight:bold">{state}</span>')
    get_status_draw.short_description = 'Статус розыгрыша'

    def get_download_link(self, obj):
        if obj:
            url = reverse('admin:telegram_bot_player_export')
            download_button_html = format_html(
                '''<a href="{}?draw={}" style="background-color: #4CAF50;border: none;
                color: white;padding: 8px 18px;text-align: center;text-decoration: none;
                f'display: inline-block;font-size: 16px;margin: 4px 2px;cursor: pointer;">Скачать</a>
                ''', url, obj.title
            )
            return mark_safe(download_button_html)
    get_download_link.short_description = 'Данные о розыгрыше'

    def get_amount_users(self, obj):
        # TODO переписать без использования поля Player.draw
        return 0  # FIXME загулшка
        # return Player.objects.filter(draw__title=obj.title).count()
    get_amount_users.short_description = 'Количество участников'


@admin.register(Rebus)
class RebusAdmin(admin.ModelAdmin):
    fields = ['image', 'get_preview_image', 'text', 'hint', 'published']
    list_filter = ['published']
    list_display = [
        'get_edit_url',
        'get_preview_image',
        'published',
        'text',
        'hint',
        'get_rebus_answers'
    ]
    readonly_fields = ['get_preview_image']
    inlines = [AnswerInline]
    search_fields = ['text', 'hint', 'answers__answer']

    def get_preview_image(self, obj):
        if not obj.image:
            return '-'
        return mark_safe(f'<img src="{obj.image.url}" height="{130}" />')
    get_preview_image.short_description = 'Предварительный просмотр изображения'

    def get_edit_url(self, obj):
        if obj.id:
            url = reverse('admin:telegram_bot_rebus_change', args=(obj.id,))
            return format_html(
                '<a href="{url}">{title}</a>', url=url, title=f'Ребус {obj.id}'
            )
    get_edit_url.short_description = 'Ребус'

    def get_rebus_answers(self, obj):
        if obj.id:
            rebus_answers = obj.answers.all()
            return [answer.answer for answer in rebus_answers]
    get_rebus_answers.short_description = 'Ответы'


@admin.register(RebusAttempt)
class RebusAttemptAdmin(admin.ModelAdmin):
    list_filter = ['success']
    list_display = [
        'rebus',
        'user',
        'get_draw',
        'success',
        'get_check_answer',
        'get_right_answers'
    ]

    def get_readonly_fields(self, request, obj=None):
        if not request.user.is_superuser:
            return [
                'rebus',
                'user',
                'answer_received_at',
                'success',
                'answer',
                'rebus_sendet_at'
            ]
        return []

    def get_right_answers(self, obj):
        rebus_answers = obj.rebus.answers.values('answer')
        answers = [answer['answer'] for answer in rebus_answers]
        return answers
    get_right_answers.short_description = 'Правильные ответы'

    def get_check_answer(self, obj):
        query_set_right_answers = obj.rebus.answers.all()
        right_answers = [answer.answer for answer in query_set_right_answers]
        if obj.answer in right_answers:
            return mark_safe(f'<span style="color:green;font-weight:bold">{obj.answer}</span>')
        return mark_safe(f'<span style="color:red;font-weight:bold">{obj.answer}</span>')
    get_check_answer.short_description = 'Ответ участника'

    def get_draw(self, obj):
        start_at = obj.answer_received_at
        end_at = obj.rebus_sendet_at
        draws = Draw.objects.filter(start_at__lte=start_at, end_at__gte=end_at).first()
        if draws:
            return draws.title
        return '-'
    get_draw.short_description = 'Розыгрыш'

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('rebus', 'user').prefetch_related('rebus__answers')


@admin.register(PollResult)
class PollResultAdmin(admin.ModelAdmin):
    list_filter = ['poll_finished']
    search_fields = ['user__full_name']
    list_display = ['user', 'poll_finished', 'ended_at']
    inlines = [PollQuestionAnswerPairInline]

    def get_readonly_fields(self, request, obj=None):
        if not request.user.is_superuser:
            return [
                'user',
                'current_question',
                'poll_finished',
                'started_at',
                'ended_at'
            ]
        return []
