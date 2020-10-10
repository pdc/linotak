# Generated by Django 3.0.8 on 2020-08-30 21:57

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('mentions', '0003_post_i18n'),
    ]

    operations = [
        migrations.AddField(
            model_name='incoming',
            name='received',
            field=models.DateTimeField(default=django.utils.timezone.now, verbose_name='received'),
        ),
    ]