# Generated by Django 2.1.4 on 2019-01-03 22:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('images', '0004_representation'),
    ]

    operations = [
        migrations.AlterField(
            model_name='representation',
            name='content',
            field=models.FileField(blank=True, help_text='Content of the image representation.', null=True, upload_to='i'),
        ),
    ]