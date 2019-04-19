from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
import factory

from ..models import Person, Series, Tag, Note, NoteSubject, Locator, wordify


class PersonFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Person

    native_name = factory.Faker('name')
    login = factory.LazyAttribute(lambda x: get_user_model().objects.create_user(
        username='.'.join(x.native_name.lower().split()),
        password='secret',
    ))


class SeriesFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Series

    name = factory.Sequence(lambda n: 'series%d' % n)
    title = factory.Sequence(lambda n: 'series%d' % n)

    @factory.post_generation
    def editors(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            for editor in extracted:
                self.editors.add(editor)
        else:
            person = PersonFactory.create()
            self.editors.add(person)


class TagFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Tag

    name = factory.Sequence(lambda n: 'tag%d' % n)
    label = factory.LazyAttribute(lambda x: wordify(x.name))


class NoteFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Note

    series = factory.SubFactory(SeriesFactory)
    text = factory.Sequence(lambda n: 'text of note %d' % n)
    author = factory.LazyAttribute(lambda x: x.series.editors.all()[0])
    published = None

    @factory.post_generation
    def tags(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            for tag in extracted:
                self.tags.add(Tag.objects.get_tag(tag))

    @factory.post_generation
    def subjects(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            for i, locator in enumerate(extracted):
                NoteSubject.objects.create(note=self, locator=locator, sequence=i)


class LocatorFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Locator

    author = factory.SubFactory(PersonFactory)
    url = factory.Sequence(lambda n: 'https://example.com/%d' % n)
    title = factory.Sequence(lambda n: 'Locator %d' % n)
    text = factory.Sequence(lambda n: 'Text of locator %d' % n)
    published = factory.Sequence(lambda n: timezone.now() - timedelta(days=n))

    @factory.post_generation
    def via(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            self.via = extracted
