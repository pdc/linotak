# Generated by Django 3.0.8 on 2020-07-11 15:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notes', '0017_auto_20200621_2139'),
    ]

    operations = [
        migrations.AddField(
            model_name='locator',
            name='sensitive',
            field=models.BooleanField(default=False, help_text='Main image is ‘sensitive’ and should be hidden by default on Mastodon.'),
        ),
    ]