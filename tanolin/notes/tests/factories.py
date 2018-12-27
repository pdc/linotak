
from django.contrib.auth import get_user_model
import factory

from ..models import Person, Series, Note


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


class NoteFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Note

    series = factory.SubFactory(SeriesFactory)
    text = factory.Sequence(lambda n: 'text of note %d' % n)
    author = factory.LazyAttribute(lambda x: x.series.editors.all()[0])
    published = None

    # @factory.post_generation
    # def author(self, create, extracted, **kwargs):
    #     if not create:
    #         return
    #     if extracted:
    #         self.author = extracted.login
    #     else:
    #         self.author = self.series.editors.all()[0]
