# Generated by Django 3.0.8 on 2020-08-30 22:34

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('customuser', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='login',
            options={'verbose_name': 'login', 'verbose_name_plural': 'logins'},
        ),
    ]