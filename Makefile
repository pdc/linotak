# Makefile because what the hell.

PYTHON=pipenv run python
SITE=ooble
PACKAGE=linotak
HOST=$(SITE)@spreadsite.org
VIRTUALENV=$(SITE)
SETTINGS=$(SITE)
SITE_DIR=/home/$(SITE)/Sites/$(PACKAGE)
JS_BUNDLE=linotak/notes/static/notes/bundle.js


all: requirements.txt $(JS_BUNDLE)


run_home=ssh $(HOST) bash -c
prefix=. /home/$(SITE)/virtualenvs/$(VIRTUALENV)/bin/activate; cd $(SITE_DIR);
manage=$(prefix) envdir /service/$(SITE)/env ./manage.py

# Push to the shared Git repo and run commands on the remote server to fetch and update.
deploy: tests requirements.txt $(JS_BUNDLE)
	git push
	echo "mkdir -p static caches/django" | ssh ooble@spreadsite.org sh
	echo "cd $(SITE_DIR); git pull" | ssh ooble@spreadsite.org sh
	echo "$(prefix) pip install -r requirements.txt" | ssh ooble@spreadsite.org sh
	echo "$(manage) migrate" | ssh ooble@spreadsite.org sh
	echo "$(manage) collectstatic --noinput" | ssh ooble@spreadsite.org sh
	echo "$(prefix) django-admin compilemessages" | ssh ooble@spreadsite.org sh

tests:
	$(PYTHON) manage.py test --keep --fail

requirements.txt: Pipfile Pipfile.lock
	pipenv lock -r > $@

$(JS_BUNDLE): editor/src/App.svelte editor/src/main.js
	cd editor && yarn && yarn build
	cp -p editor/public/build/bundle.* linotak/notes/static/notes/
