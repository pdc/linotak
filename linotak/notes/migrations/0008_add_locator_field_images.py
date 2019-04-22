# Generated by Django 2.1.7 on 2019-03-23 10:06

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('images', '0007_validate_media_type'),
        ('notes', '0007_rename_locator_images_legacy'),
    ]

    operations = [
        migrations.CreateModel(
            name='LocatorImage',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('prominence', models.PositiveSmallIntegerField(default=0)),
                ('image', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='images.Image')),
                ('locator', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='notes.Locator')),
            ],
            options={
                'ordering': ['-prominence'],
            },
        ),
        migrations.AddField(
            model_name='locator',
            name='images',
            field=models.ManyToManyField(related_name='occurences', related_query_name='occurrence', through='notes.LocatorImage', to='images.Image'),
        ),
        migrations.AlterUniqueTogether(
            name='locatorimage',
            unique_together={('locator', 'image')},
        ),
    ]