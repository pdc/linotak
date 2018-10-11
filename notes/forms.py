"""Forms for use in the notes app."""

from django.forms import (
    Form, ModelForm, formset_factory,
    CharField, DateTimeField, URLField,
    HiddenInput, Textarea,
)

from .models import Note, Locator, NoteSubject


class NoteForm(ModelForm):
    """Form for creating or editing a note."""

    class Meta:
        model = Note
        fields = ['text', 'series', 'author']

        widgets = {
            'text': Textarea(attrs={'cols': 80, 'rows': 3}),
            'series': HiddenInput(),
            'author': HiddenInput(),
        }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.subjects_formset = LocatorFormset(
            prefix='subj',
            data=kwargs.get('data'),
            initial=[
                {'url': x.url, 'title': x.title, 'text': x.text, 'published': x.published}
                for x in self.instance.subjects.order_by('notesubject__sequence')
            ] if self.instance and self.instance.pk else [],
        )

    def clean(self):
        """Validate the subjects as well."""
        self.subjects_formset.clean()
        return super().clean()

    def is_valid(self):
        return super().is_valid() and self.subjects_formset.is_valid()

    def save(self, **kwargs):
        """Ensure subject locators are copied to the form."""
        instance = super().save(
            **kwargs)

        subject_forms = (
            sorted(self.subjects_formset.initial_forms, key=lambda f: int(f.cleaned_data['ORDER']))
            + [f for f in self.subjects_formset.extra_forms if f.has_changed()])
        subject_forms = [f for f in subject_forms if not f.cleaned_data['DELETE']]
        for i, locator in enumerate(x.save(**kwargs) for x in subject_forms):
            arc, is_new = NoteSubject.objects.get_or_create(note=instance, locator=locator, defaults={'sequence': i})
            if not is_new and arc.sequence != i:
                arc.sequence = i
                arc.save()
        if instance.extract_subject():
            instance.save()
        return instance


class LocatorForm(Form):
    url = URLField(label='URL', max_length=Locator._meta.get_field('url').max_length)
    title = CharField(label='Title (optional)', required=False, max_length=Locator._meta.get_field('title').max_length)
    text = CharField(label='Text (optional)', required=False, widget=Textarea)
    published = DateTimeField(label='Published (if known)', required=False)

    def __init__(self, data=None, instance=None, **kwargs):
        self.instance = instance
        super().__init__(data, **kwargs)

    def save(self):
        if self.errors:
            raise ValueError("The locator could not be created/changed because the data didn't validate.")
        defaults = {
            'title': self.cleaned_data['title'],
            'text': self.cleaned_data['text'],
            'published': self.cleaned_data['published'],
        }
        locator, is_new = Locator.objects.get_or_create(url=self.cleaned_data['url'], defaults=defaults)
        if not is_new:
            dirty = False
            for k, v in defaults.items():
                if v:
                    setattr(locator, k, v)
                    dirty = True
            if dirty:
                locator.save()
        return locator

    @classmethod
    def initial_from_instance(cls, locator):
        """Get a suitable value for initial argument to constructor from this Locator instance."""
        return {
            'url': locator.url,
            'title': locator.title,
            'text': locator.text,
            'published': locator.published,
        }


LocatorFormset = formset_factory(LocatorForm, extra=0, can_order=True, can_delete=True)
