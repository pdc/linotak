# Generated by Django 3.0.8 on 2020-10-11 14:43

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("images", "0011_image_placeholder"),
    ]

    operations = [
        migrations.AlterField(
            model_name="image",
            name="focus_x",
            field=models.FloatField(
                default=0.5,
                help_text="Range 0.0 to 1.0. Fraction of the way from the left edge of the focal point",
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
                help_text="Range 0.0 to 1.0. Fraction of the way down from the top of the focal point",
                validators=[
                    django.core.validators.MinValueValidator(0.0),
                    django.core.validators.MaxValueValidator(1.0),
                ],
                verbose_name="focus y",
            ),
        ),
    ]
