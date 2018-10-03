from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from customuser.models import Login
from ..models import Series, Locator


class TestNoteList(TestCase):
    def setUp(self):
        self.client = Client()

    def test_includes_series(self):
        series = Series.objects.create(title='Foo', name='bar')

        r = self.client.get('/notes/bar/')

        self.assertEqual(r.context['series'], series)

    def test_excludes_unpublished_notes(self):
        series = Series.objects.create(title='Foo', name='bar')
        author = Login.objects.create_user(username='alice', password='secret')
        note1 = series.note_set.create(text='note1', author=author)
        note2 = series.note_set.create(text='note2', author=author, published=timezone.now())

        self.client.logout()
        r = self.client.get('/notes/bar/')

        self.assertEqual(list(r.context['note_list']), [note2])
        self.assertFalse(r.context.get('has_draft'))

    def test_includes_unpublished_notes_if_editor(self):
        series = Series.objects.create(title='Foo', name='bar')
        author = Login.objects.create_user(username='alice', password='secret')
        series.editors.add(author)
        series.save()
        note1 = series.note_set.create(text='The Note', author=author)

        self.client.login(username='alice', password='secret')
        r = self.client.get('/notes/bar/')

        self.assertEqual(list(r.context['note_list']), [note1])
        self.assertTrue(r.context['has_draft'])


class TestNoteUpdateView(TestCase):
    def setUp(self):
        self.client = Client()

    def test_redirects_permenently_if_published(self):
        note = self.create_note(published=timezone.now())

        self.client.login(username='alice', password='secret')
        r = self.client.get('/notes/bar/%d/edit' % (note.pk,), follow=True)

        self.assertEqual(r.redirect_chain, [('/notes/bar/%d' % (note.pk,), 301)])

    def test_passes_series_and_author(self):
        self.create_series()
        Locator.objects.create(url='http://example.com/1')
        Locator.objects.create(url='http://example.com/2')

        self.client.login(username='alice', password='secret')
        r = self.client.get('/notes/bar/new')

        self.assertEqual(r.context['form'].initial['series'], self.series)
        self.assertEqual(r.context['form'].initial['author'], self.alice)

    def test_creates_note_on_post(self):
        self.create_series()

        self.client.login(username='alice', password='secret')
        r = self.client.post('/notes/bar/new', {
            'series': str(self.series.pk),  # From intitial
            'author': str(self.alice.pk),
            'text': 'NOTE TEXT',
            'subj-TOTAL_FORMS': '1',
            'subj-INITIAL_FORMS': '0',
            'subj-MIN_NUM_FORMS': '0',
            'subj-MAX_NUM_FORMS': '1000',
            'subj-0-url': 'https://example.com/NOTE-URL',
            'subj-0-title': '',
            'subj-0-text': '',
            'subj-0-published': '',
            'subj-0-ORDER': '',
            'subj-0-id': '',
        }, follow=True)

        self.assertFalse('form' in r.context and r.context['form'].errors)

        # Redirected to new note.
        self.assertTrue(r.context.get('note'))
        note = r.context['note']
        self.assertEqual(note.text, 'NOTE TEXT')
        self.assertTrue(note.subjects.all())
        self.assertEqual(note.subjects.all()[0].url, 'https://example.com/NOTE-URL')

    def create_series(self):
        self.series = Series.objects.create(title='Foo', name='bar')
        self.alice = Login.objects.create_user(username='alice', password='secret')
        self.series.editors.add(self.alice)
        self.series.save()

    def create_note(self, **kwargs):
        self.create_series()
        note_kwargs = {
            'text': 'Note text',
            'author': self.alice,
        }
        note_kwargs.update(kwargs)
        note = self.series.note_set.create(**note_kwargs)
        return note
