from getpass import getpass

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from accounts.models import Role, User


class Command(BaseCommand):
    help = 'Crée un gérant (nom + PIN). Sert à créer le premier utilisateur d\'une installation neuve.'

    def add_arguments(self, parser):
        parser.add_argument('name')
        parser.add_argument('--pin', help='PIN de 4 à 6 chiffres (demandé si absent)')

    def handle(self, *args, name, pin=None, **options):
        if User.objects.filter(name=name).exists():
            raise CommandError(f'Un utilisateur nommé « {name} » existe déjà.')
        if pin is None:
            pin = getpass('PIN (4 à 6 chiffres) : ')
        try:
            User.objects.create_user(name, pin, Role.MANAGER)
        except ValidationError as e:
            raise CommandError(' '.join(e.messages))
        self.stdout.write(self.style.SUCCESS(f'Gérant « {name} » créé.'))
