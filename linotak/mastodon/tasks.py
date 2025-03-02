"""Tasks that may be queued on Celery."""

from celery import shared_task
from celery.utils.log import get_task_logger

from .models import Post

logger = get_task_logger(__name__)


@shared_task(name="linotak.mastodon.post_post_to_mastodon")
def post_post_to_mastodon(pk):
    """Attempt to post the post with this ID to mastodon."""
    try:
        post = Post.objects.get(pk=pk)
        post.post_to_mastodon()
        logger.info(f"posted note {post.note.pk} ({post.note}) to {post.connection}")
    except Post.DoesNotExist:
        logger.warning(f"{pk}: post does not exist")
