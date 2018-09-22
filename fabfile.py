# -*-coding: UTF-8 -*-
# Run these commands with fab

from datetime import date, datetime
from fabric.api import local, settings, abort, run, cd, env, sudo, prefix
from fabric.contrib.console import confirm
from fabric.contrib.files import exists

env.site_name = 'ooble'
env.package_name = 'linotak'
env.hosts = ['{0}@spreadsite.org'.format(env.site_name)]
env.virtualenv = env.site_name
env.settings_subdir = env.site_name
env.django_apps = ['notes', 'customuser']


def update_requirements():
    local("pipenv lock -r > requirements.txt")


def test():
    with settings(warn_only=True):
        result = local('pipenv run python manage.py test {0}'.format(' '.join(env.django_apps)), capture=True)
    if result.failed and not confirm("Tests failed. Continue anyway?"):
        abort("Aborting at user request.")


def push():
    local('git push')


def deploy():
    test()
    push()

    run('if [ ! -d static ]; then mkdir static; fi')
    #  run('mkdir -p caches/httplib2')
    run('mkdir -p caches/django')

    code_dir = '/home/%s/Sites/%s' % (env.site_name, env.package_name)
    with cd(code_dir):
        run('git pull')
        with prefix('. /home/%s/virtualenvs/%s/bin/activate' % (env.site_name, env.virtualenv)):
            run('pip install -r requirements.txt')
            run('envdir /service/%s/env ./manage.py collectstatic --noinput' % (env.site_name,))


def make_virtualenv():
    env_name = 'virtualenvs/{0}'.format(env.site_name)
    if exists(env_name):
        bak_name = 'virtualenvs/before-{0}.{1}'.format(date.today().isoformat(), env.site_name)
        if not exists(bak_name):
            run('mv {0} {1}'.format(env_name, bak_name))
    run('virtualenv {0}'.format(env_name))