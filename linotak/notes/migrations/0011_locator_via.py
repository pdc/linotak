# Generated by Django 2.1.7 on 2019-04-07 18:52

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("notes", "0010_remove_locator_legacy_images"),
    ]

    operations = [
        migrations.AddField(
            model_name="locator",
            name="via",
            field=models.ForeignKey(
                blank=True,
                help_text="linm to another locator that referenced this one",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="destinatons",
                related_query_name="destination",
                to="notes.Locator",
            ),
        ),
    ]
