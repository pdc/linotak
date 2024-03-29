# Generated by Django 2.1.4 on 2019-02-02 23:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notes", "0005_add_table_tag"),
    ]

    operations = [
        migrations.AlterField(
            model_name="note",
            name="tags",
            field=models.ManyToManyField(
                blank=True,
                related_name="occurences",
                related_query_name="occurrence",
                to="notes.Tag",
            ),
        ),
    ]
