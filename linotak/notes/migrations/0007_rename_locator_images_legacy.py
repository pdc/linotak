# Generated by Django 2.1.7 on 2019-03-23 10:05

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('notes', '0006_notes_tags_blank'),
    ]

    operations = [
        migrations.RenameField(
            model_name='locator',
            old_name='images',
            new_name='legacy_images',
        ),
    ]