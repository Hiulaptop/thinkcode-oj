from django.core.management.base import BaseCommand, CommandError

from judge.utils.problem_releases import publish_problem_to_r2


class Command(BaseCommand):
    help = 'Publish a local problem directory as a versioned Cloudflare R2 release.'

    def add_arguments(self, parser):
        parser.add_argument('code')
        parser.add_argument('version', nargs='?', default=None)

    def handle(self, *args, **options):
        try:
            manifest = publish_problem_to_r2(options['code'], options['version'])
        except Exception as e:
            raise CommandError(str(e)) from e
        self.stdout.write(self.style.SUCCESS(
            f'Published {manifest["code"]}@{manifest["version"]} ({manifest["sha256"]})',
        ))
