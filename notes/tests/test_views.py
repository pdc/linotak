from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from customuser.models import Login
from ..models import Series


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
        series = Series.objects.create(title='Foo', name='bar')
        author = Login.objects.create_user(username='alice', password='secret')
        series.editors.add(author)
        series.save()
        note = series.note_set.create(text='The Note', author=author, published=timezone.now())

        self.client.login(username='alice', password='secret')
        r = self.client.get('/notes/bar/%d/edit' % (note.pk,), follow=True)

        self.assertEqual(r.redirect_chain, [('/notes/bar/%d' % (note.pk,), 301)])

