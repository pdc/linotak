# Generated by Django 2.1.4 on 2018-12-29 11:35

import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('images', '0003_image_retrieved'),
    ]

    operations = [
        migrations.CreateModel(
            name='Representation',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content', models.FileField(blank=True, help_text='Content of the image representation.', null=True, upload_to='img')),
                ('media_type', models.CharField(max_length=200, validators=[django.core.validators.RegexValidator('^(image|application)/\\w+(;\\s*\\w+=.*)?$')])),
                ('width', models.PositiveIntegerField()),
                ('height', models.PositiveIntegerField()),
                ('is_cropped', models.BooleanField()),
                ('etag', models.BinaryField(help_text='Hash of the image data when generated.', max_length=16)),
                ('created', models.DateTimeField(default=django.utils.timezone.now)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('image', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='representations', related_query_name='representation', to='images.Image')),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='representation',
            unique_together={('image', 'width', 'is_cropped')},
        ),
    ]