import os

from django.core.management.base import BaseCommand, CommandError

from ...scanner import PageScanner


class Command(BaseCommand):
    help = "Scan a file as if it were a downloaded page."
    # requires_migrations_checks = True
    # requires_system_checks = False

    def add_arguments(self, parser):
        parser.add_argument(
            "files",
            nargs="+",
            help="File(s) to examine for links.",
        )
        parser.add_argument(
            "--base-url",
            "-b",
            help="Specifies base URL.",
        )

    def handle(self, *args, **options):
        for file_path in options["files"]:
            scanner = PageScanner(
                options["base_url"] or "file://" + os.path.abspath(file_path)
            )
            with open(file_path, "r", encoding="UTF-8") as input:
                scanner.feed(input.read())
            scanner.close()
            for thing in scanner.stuff:
                self.stdout.write(repr(thing))
