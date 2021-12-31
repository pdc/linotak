# Generated by Django 2.1.3 on 2018-11-18 17:06

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Locator",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("url", models.URLField(max_length=1000, unique=True)),
                ("title", models.CharField(blank=True, max_length=250)),
                (
                    "text",
                    models.TextField(
                        blank=True,
                        help_text="Description, summary, or content of the linked-to resource",
                    ),
                ),
                ("published", models.DateTimeField(blank=True, null=True)),
                ("created", models.DateTimeField(default=django.utils.timezone.now)),
                ("modified", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="Note",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "text",
                    models.TextField(
                        blank=True,
                        help_text="Content of note. May be omitted if it has subject links.",
                    ),
                ),
                ("created", models.DateTimeField(default=django.utils.timezone.now)),
                ("modified", models.DateTimeField(auto_now=True)),
                ("published", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "ordering": ["-published", "-created"],
            },
        ),
        migrations.CreateModel(
            name="NoteSubject",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("sequence", models.PositiveSmallIntegerField(default=0)),
                (
                    "locator",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="notes.Locator"
                    ),
                ),
                (
                    "note",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="notes.Note"
                    ),
                ),
            ],
            options={
                "ordering": ["sequence"],
            },
        ),
        migrations.CreateModel(
            name="Person",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "native_name",
                    models.CharField(
                        help_text="How this user’s name is presented.", max_length=250
                    ),
                ),
                (
                    "login",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Profile",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("url", models.URLField(max_length=1000)),
                (
                    "label",
                    models.CharField(
                        help_text="How to display the username or equivalent for this person on this site. E.g., @damiancugley if on twitter.",
                        max_length=250,
                    ),
                ),
                (
                    "person",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="profiles",
                        related_query_name="profile",
                        to="notes.Person",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Series",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.SlugField(help_text="Used in URLs", max_length=63)),
                ("title", models.CharField(max_length=250)),
                (
                    "desc",
                    models.TextField(
                        blank=True,
                        help_text="Optional description.",
                        verbose_name="description",
                    ),
                ),
                ("created", models.DateTimeField(default=django.utils.timezone.now)),
                ("modified", models.DateTimeField(auto_now=True)),
                ("editors", models.ManyToManyField(to="notes.Person")),
            ],
            options={
                "verbose_name_plural": "series",
                "ordering": ["title"],
            },
        ),
        migrations.AddField(
            model_name="note",
            name="author",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to="notes.Person"
            ),
        ),
        migrations.AddField(
            model_name="note",
            name="series",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to="notes.Series"
            ),
        ),
        migrations.AddField(
            model_name="note",
            name="subjects",
            field=models.ManyToManyField(
                help_text="Web page or sites that is described or cited in this note.",
                related_name="occurences",
                related_query_name="occurrence",
                through="notes.NoteSubject",
                to="notes.Locator",
            ),
        ),
        migrations.AddField(
            model_name="locator",
            name="author",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="notes.Person",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="notesubject",
            unique_together={("note", "locator")},
        ),
    ]
