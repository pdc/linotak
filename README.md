# Linotak: Link-Note Taker

In other words, yet another micro-blogging app! This one powers [pdc.ooble.uk].

This app intentionally has minimal features, and does not have interaction features,
other than for editors of the site.

##  Development

Stack:

* Python 3.10
* Django 5.2
* Celery 5.5
* ImageMagick 7


## Setting up

The Linotak  Notes app  is designed to run a limited number of note-taking sites, which we call _series_,
as in a series of notes. Each series has its own subdomain, and can have its author/editor or team of authors/editors.
For example, if it is set up with a domain of `notes.example`,
Alice and Bob might have respective sites `https://alice.notes.example/` and `https://blather.notes.example/`.

Linotak has no support for online user enrolling, customer managemenet or subscriptions:
it is intended for small-scale deployments, when the site admin knows the editors
and any commercial arrangements are arranged elsewhere. New series and logins are
created through Django’s admin pages:



### Post-install

To set up a series for Marcus Valerius Martialis to publish epigrams:

1. In the admin site Customuser section, create a login  with username `martial`.
2. In the Notes section, create a person whose login is `martial` and native name is `Marcus Valerius Martialis`.
3. Also under Notes, create a series with name `epigrams` and title `Martial’s Epigrams`.
4. Outside of Linotak, set up the domain name `epigrams.notes.example` and its TLS certificate (More details below).

Now Martial should be able to visit `https://epigrams.notes.example/new` to log in and create his first note.

We need TLS certificates so that HTTPS works: either certificates for each series, or a wildcard certificate, which is more complicated.
For small-scale deployments, it is easier to use [Let’s Encrypt] with an explicit list of the subdomains.

## Development

We need to start by creating fake domains to support the series middleware. On
most Unix-like systems (like macOS and GNU/Linux) we do this by editing `/etc/hosts`.



We are using Poetry to organize the dependencies.

```sh
poetry install
eval $(poetry env activate)
```

Running tests

```sh
./manage.py check
./manage.py test
```

Server settings are controlled by environment variables; for development we can
add them to a file `.env`, which is *not* added to source-code control.

```sh
echo >>.emv DEBUG=y
```

Celery needs a message broker. I use RabbitMQ


Running the server works easiest with 3 terminal windows running the following commands:

```sh
rabbitmq-server
poetry run -- celery -A ooblesite.celery worker --loglevel=info
poetry run -- ./manage.py runserver 0:8004
```

##  Testing scanning

Try this

    URL=https://foo.example.com/bar
    FILE=samples/foobar.html

    curl $URL > $FILE
    poetry run -- ./manage.py linotakscan --base=$URL $FILE


## Localization

Freshen the extracted translation files with

    poetry run -- django-admin makemessages -l eo

Upload `.po` files to <POEditor.com> and download and then run

    poetry run -- django-admin compilemessages


## Bookmarklet

Edit the following URL

    javascript:location.href='https://pdc.ooble.uk/new?u='+encodeURIComponent(location.href)+'&t='+encodeURIComponent(document.title)


## Setting up RabbitMQ

RabbitMQ is the AMQP implementation we use to coordinate Celery’s task queues.

Assuming your site is called, say, `example.com` config is easier if we consistently
use the name `example` when creating databases etc., and so we will use it for
the RabbitMQ virtual host and user. In a production site we can use a utility like
`pwgen` to create passwords.

```sh
ENV=/home/example/env
SITE=example
PW=$(pwgen 40)

rabbitmqctl enable_feature_flag all
rabbitmqctl add_user $SITE $PW
rabbitmqctl add_vhost $SITE
rabbitmqctl set_permissions -p $SITE $SITE ".*" ".*" ".*"
echo >>$ENV CELERY_BROKER_URL=amqp://$SITE:$PW@localhost/$SITE
```

[pdc.ooble.uk]: https://pdc.ooble.uk/
[rel-syndication]: http://microformats.org/wiki/rel-syndication
[Mastodon API]: https://github.com/tootsuite/documentation/blob/master/Using-the-API/API.md
[WebMention]: https://www.w3.org/TR/webmention/
[Microformats2]: http://microformats.org/wiki/microformats2
[Translation]: https://docs.djangoproject.com/en/3.0/topics/i18n/translation/
[Let’s Encrypt]: https://letsencrypt.org
[correct-horse-battery-staple]: https://xkcd.com/936/
