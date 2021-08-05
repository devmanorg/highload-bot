import csv
import tempfile

from django.urls import reverse
from django.http import HttpResponseRedirect, HttpResponse

from .models import PollResult, PollQuestionAnswerPair


def redirect2admin(request):
    return HttpResponseRedirect(reverse('admin:index'))


def write_to_file(tmp_file, serialized_polls=[], questions_fields=[]):
    with open(tmp_file.name, 'w') as poll_file:
        fields_names = ['Имя и фамилия', 'Номер телефона']
        poll_writer = csv.DictWriter(
            poll_file,
            delimiter=',',
            quotechar='"',
            quoting=csv.QUOTE_MINIMAL,
            fieldnames=fields_names + questions_fields
        )
        poll_writer.writeheader()
        for serialized_poll in serialized_polls:
            poll_writer.writerow(serialized_poll)


def prepare_poll_result_file_for_download(tmp_file):
    polls = PollResult.objects.filter(poll_finished=True, user__exclude_from_export=False)
    all_paris_questions_answers = PollQuestionAnswerPair.objects.values('question').distinct()
    questions_fields = [pair['question'] for pair in all_paris_questions_answers]
    if not polls:
        write_to_file(tmp_file)
        return
    serialized_polls = [{
        'Имя и фамилия': poll.user.full_name,
        'Номер телефона': poll.user.phone_number,
        **{pair.question: pair.answer for pair in poll.poll_question_answer_pairs.all()},
    } for poll in polls]
    write_to_file(tmp_file, serialized_polls, questions_fields)


def download_result_polls_in_csv(request, format=None):
    tmp_file = tempfile.NamedTemporaryFile(suffix='.csv')
    prepare_poll_result_file_for_download(tmp_file)
    with open(tmp_file.name, 'r') as csv_file:
        output_file_name = 'PollResults.csv'
        response = HttpResponse(csv_file.read(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{output_file_name}"'
    return response
