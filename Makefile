# Makefile because what the hell.

PYTHON=pipenv run python
SITE=ooble
PACKAGE=linotak
HOST=$(SITE)@spreadsite.org
VIRTUALENV=$(SITE)
SETTINGS=$(SITE)
SITE_DIR=/home/$(SITE)/Sites/$(PACKAGE)

all: requirements.txt


run_home=ssh $(HOST) bash -c
prefix=. /home/$(SITE)/virtualenvs/$(VIRTUALENV)/bin/activate; cd $(SITE_DIR);
manage=$(prefix) envdir /service/$(SITE)/env ./manage.py

# Push to the shared Git repo and run commands on the remote server to fetch and update.
deploy: tests requirements.txt
	git push
	echo "mkdir -p static caches/django" | ssh ooble@spreadsite.org sh
	echo "cd $(SITE_DIR); git pull" | ssh ooble@spreadsite.org sh
	echo "$(prefix) pip install -r requirements.txt" | ssh ooble@spreadsite.org sh
	echo "$(manage) migrate" | ssh ooble@spreadsite.org sh
	echo "$(manage) collectstatic --noinput" | ssh ooble@spreadsite.org sh

tests:
	$(PYTHON) manage.py test --keep --fail

requirements.txt: Pipfile Pipfile.lock
	pipenv -r > $@
