Linotak: Link-Note Taker
========================

In other words, yet another micro-blogging app! This one powers [pdc.ooble.uk][].



Development
-----------

Stack:

  * Django 3.2
  * Celery 4.4
  * Python 3.8

Use Poetry:

    poetry run -- ./manage.py test
    poetry run -- celery -A linotak.celery worker --loglevel=info
    poetry run -- ./manage.py runserver 0:8004

Or use `poetry shell` to avoid typing `poetry run` all the time.


Testing scanning
----------------

Try this

    URL=https://foo.example.com/bar
    FILE=samples/foobar.html

    curl $URL > $FILE
    poetry run -- ./manage.py linotakscan --base=$URL $FILE


Localization
------------

Freshen the extracted translation files with

    poetry run -- django-admin makemessages -l eo

Upload `.po` files to <POEditor.com> and download and then run

    poetry run -- django-admin compilemessages


Bookmarklet
-----------

Edit the following URL

    javascript:location.href='https://pdc.ooble.uk/new?u='+encodeURIComponent(location.href)+'&t='+encodeURIComponent(document.title)




  [pdc.ooble.uk]: https://pdc.ooble.uk/
  [rel-syndication]: http://microformats.org/wiki/rel-syndication
  [Mastodon API]: https://github.com/tootsuite/documentation/blob/master/Using-the-API/API.md
  [WebMention]: https://www.w3.org/TR/webmention/
  [Microformats2]: http://microformats.org/wiki/microformats2
  [Translation]: https://docs.djangoproject.com/en/3.0/topics/i18n/translation/
