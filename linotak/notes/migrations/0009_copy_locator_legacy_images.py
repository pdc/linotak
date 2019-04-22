# Generated by Django 2.1.7 on 2019-03-23 10:06

from django.db import migrations


def copy_legacy_to_images(apps, schema_editor):
    """Copy from legacy images to new model-backed images."""
    Locator = apps.get_model("notes", "Locator")
    LocatorImage = apps.get_model("notes", "LocatorImage")
    db_alias = schema_editor.connection.alias
    for locator in Locator.objects.using(db_alias).all():
        LocatorImage.objects.using(db_alias).bulk_create([
            LocatorImage(locator=locator, image=image)
            for image in locator.legacy_images.all()
        ])


def copy_images_to_legacy(apps, schema_editor):
    """Copy from model-backed images to legacy images.

    For reversing migration.
    """
    Locator = apps.get_model("notes", "Locator")
    db_alias = schema_editor.connection.alias
    for locator in Locator.objects.using(db_alias).all():
        locator.legacy_images.add([locator.images])


class Migration(migrations.Migration):

    dependencies = [
        ('notes', '0008_add_locator_field_images'),
    ]

    operations = [
        migrations.RunPython(copy_legacy_to_images, copy_images_to_legacy)
    ]