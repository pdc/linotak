title: Celery 5.6.3 versus RabbitMQ 4.3.2
author: Damian Cugley
tags:
- Celery
- RabbitMQ

Linotak is a side project I return to from time to time. Whenever I return to
change something, I have to rediscover how to run it locally. So I put that in
the README.

> Running the server works easiest with 3 terminal windows running the following commands:

> ```sh
> rabbitmq-server
> poetry run -- celery -A ooblesite.celery worker --loglevel=info
> poetry run -- ./manage.py runserver 0:8004
> ```

I always forget at first, and this usually results in an exception while rendering
the first page, as it attempts to queue an image-resizing task.

## This bout’s blocker

This time I was further thwarted by the Celery window’s being flooded with
exceptions ending with this message:

> amqp.exceptions.InternalError: Queue.declare: (541) INTERNAL_ERROR - Feature `transient_nonexcl_queues` is deprecated.
> By default, this feature is not permitted anymore.
> The feature will be removed from a future major RabbitMQ version, regardless of the configuration; actual version to be determined.

The [explanation] of this simple enough. Celery’s wants to create queues that are
transient and non-exclusive, and RabbitMQ is deprecating and removing that option.

## Workaround

The workaround for now (assuming I don’t want to just roll RabbitMQ back a version
or two) is to enable the deprecated feature. The configuration file in question is not
at `/etc/rabbitmq/rabbitmq.conf`, alas!, but instead at a location specified in
`/opt/homebrew/etc/rabbitmq/rabbitmq-env.conf`. So the fix for my macOS system
was

```sh
echo deprecated_features.permit.transient_nonexcl_queues = true >> /opt/homebrew/etc/rabbitmq/rabbitmq
```

Followed by restarting RabbitMQ server and Celery.

## Fix

There is a fix to avoid using the deprecated feature in Celery 5.7.0 (at the time
of writing the latest stable version is 5.6.3).

This addresses running the server locally on my MacBook Air. I will need to take
care when I upgrade RabbitMQ on the deployed server to either set the deprecated
flag or wait until I can upgrade Celery at the same time.




[explanation]: https://stackoverflow.com/a/79946538
