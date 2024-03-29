# Generated by Django 3.0.8 on 2020-07-26 20:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("images", "0008_auto_20200621_2139"),
    ]

    operations = [
        migrations.AddField(
            model_name="image",
            name="focus_x",
            field=models.FloatField(
                default=0.5,
                help_text="Range 0.0 to 1.0. Fraction of the way from the left edge of the focal point",
                verbose_name="focus_x",
            ),
        ),
        migrations.AddField(
            model_name="image",
            name="focus_y",
            field=models.FloatField(
                default=0.5,
                help_text="Range 0.0 to 1.0. Fraction of the way down from the top of the focal point",
                verbose_name="focus_y",
            ),
        ),
    ]
