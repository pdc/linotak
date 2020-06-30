# Generated by Django 3.0.5 on 2020-06-29 21:17

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('notes', '0017_auto_20200621_2139'),
        ('mastodon', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Post',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('their_id', models.CharField(help_text='Identifies the post in the scope of the instance', max_length=255, verbose_name='their ID')),
                ('url', models.URLField(help_text='Canonical web page of the post', max_length=1024, verbose_name='URL')),
                ('created', models.DateTimeField(default=django.utils.timezone.now, verbose_name='created')),
                ('modified', models.DateTimeField(auto_now=True, verbose_name='modified')),
                ('connection', models.ForeignKey(help_text='Mastodon instance where this note was created', null=True, on_delete=django.db.models.deletion.SET_NULL, to='mastodon.Connection', verbose_name='connection')),
                ('note', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='notes.Note', verbose_name='note')),
            ],
            options={
                'verbose_name': 'post',
                'verbose_name_plural': 'posts',
                'ordering': ('-created',),
                'unique_together': {('connection', 'note')},
            },
        ),
    ]
