# Makefile because what the hell.

PYTHON=poetry run python
SITE=ooble
PACKAGE=linotak
HOST=$(SITE)@spreadsite.org
VIRTUALENV=$(SITE)
SETTINGS=$(SITE)
SITE_DIR=/home/$(SITE)/Sites/$(PACKAGE)
JS_BUNDLE=linotak/notes/static/notes/bundle.js


all:  $(JS_BUNDLE)


run_home=ssh $(HOST) bash -c
prefix=. /home/$(SITE)/virtualenvs/$(VIRTUALENV)/bin/activate; cd $(SITE_DIR);
manage=$(prefix) envdir /service/$(SITE)/env ./manage.py

tests:
	$(PYTHON) manage.py test --keep --fail

$(JS_BUNDLE): editor.next/src/main.ts editor.next/src/naked.ts
	cd editor.next && npm install && npm run build
	cp -p editor.next/dist/assets/index*.js linotak/notes/static/notes/bundle.js
