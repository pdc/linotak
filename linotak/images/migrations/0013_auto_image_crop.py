# Generated by Django 3.0.8 on 2021-01-03 19:53

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("images", "0012_add_image_focus_validation"),
    ]

    operations = [
        migrations.AddField(
            model_name="image",
            name="crop_height",
            field=models.FloatField(
                default=1.0,
                help_text="Range 0.0 to 1.0. Fraction of the way from top toward bottom",
                validators=[
                    django.core.validators.MinValueValidator(0.0),
                    django.core.validators.MaxValueValidator(1.0),
                ],
                verbose_name="crop height",
            ),
        ),
        migrations.AddField(
            model_name="image",
            name="crop_left",
            field=models.FloatField(
                default=0.0,
                help_text="Range 0.0 to 1.0. Fraction of the way from the left edge",
                validators=[
                    django.core.validators.MinValueValidator(0.0),
                    django.core.validators.MaxValueValidator(1.0),
                ],
                verbose_name="crop left",
            ),
        ),
        migrations.AddField(
            model_name="image",
            name="crop_top",
            field=models.FloatField(
                default=0.0,
                help_text="Range 0.0 to 1.0. Fraction of the way down from the top",
                validators=[
                    django.core.validators.MinValueValidator(0.0),
                    django.core.validators.MaxValueValidator(1.0),
                ],
                verbose_name="crop top",
            ),
        ),
        migrations.AddField(
            model_name="image",
            name="crop_width",
            field=models.FloatField(
                default=1.0,
                help_text="Range 0.0 to 1.0. Fraction of the way from left toward right",
                validators=[
                    django.core.validators.MinValueValidator(0.0),
                    django.core.validators.MaxValueValidator(1.0),
                ],
                verbose_name="crop width",
            ),
        ),
        migrations.AlterField(
            model_name="image",
            name="cached_data",
            field=models.FileField(
                blank=True,
                help_text="A copy of the image data",
                null=True,
                upload_to="cached-images",
                verbose_name="cached data",
            ),
        ),
        migrations.AlterField(
            model_name="image",
            name="focus_x",
            field=models.FloatField(
                default=0.5,
                help_text="Range 0.0 to 1.0. Fraction of the way from the left edge",
                validators=[
                    django.core.validators.MinValueValidator(0.0),
                    django.core.validators.MaxValueValidator(1.0),
                ],
                verbose_name="focus x",
            ),
        ),
        migrations.AlterField(
            model_name="image",
            name="focus_y",
            field=models.FloatField(
                default=0.5,
                help_text="Range 0.0 to 1.0. Fraction of the way down from the top",
                validators=[
                    django.core.validators.MinValueValidator(0.0),
                    django.core.validators.MaxValueValidator(1.0),
                ],
                verbose_name="focus y",
            ),
        ),
    ]
