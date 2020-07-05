from django.conf import settings
from django.db import transaction

from .models import Post
from . import tasks


def handle_note_post_save(sender, instance, created, raw, **kwargs):
    """Called when note saved.

    If it is published, is in a series with connections to othere sites,
    and has not been posted, then post it.
    """
    if not raw and instance.published:
        post_is_news = [
            Post.objects.get_or_create(note=instance, connection=connection)
            for connection in instance.series.mastodon_connections.all()
        ]
        if settings.MASTODON_POST_STATUSES:
            for post, _ in post_is_news:
                if not post.posted:
                    transaction.on_commit(lambda: tasks.post_post_to_mastodon.delay(post.pk))
