Linotak: Link-Note Taker
========================

In other words, yet another micro-blogging app! This one powers [pdc.oobke.uk][].



Development
-----------

Stack:

  * Django
  * Celery
  * Python 3

Use Pipenv:

    pipenv run ./manage.py test
    pipenv run celery -A linotak.celery worker --loglevel=info
    pipenv run ./manage.py runserver 0:8004

  [pdc.ooble.uk]: https://pdc.ooble.uk/
  [rel-syndication]: http://microformats.org/wiki/rel-syndication
  [Mastodon API]: https://github.com/tootsuite/documentation/blob/master/Using-the-API/API.md
  [WebMention]: https://www.w3.org/TR/webmention/
  [Microformats2]: http://microformats.org/wiki/microformats2
