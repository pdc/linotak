Linotak: Link Note-Taker
========================

Just a sketch for now.


Development
-----------

Stack:

  * Python 3
  * Django
  * Celery

Use Pipenv:

    pipenv run ./manage.py test
    pipenv run celery -A linotak.celery worker --loglevel=info
    pipenv run ./manage.py runserver 0:8004

  [rel-syndication]: http://microformats.org/wiki/rel-syndication
  [Mastodon API]: https://github.com/tootsuite/documentation/blob/master/Using-the-API/API.md
  [WebMention]: https://www.w3.org/TR/webmention/
  [Microformats2]: http://microformats.org/wiki/microformats2
