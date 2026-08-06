
from django.core.management.base import BaseCommand
 
from accounts.models import User
from core.models import Client
from core.sync_1c import normalize_phone
 
 
class NormalizePhonesCommand(BaseCommand):
    help = 'Приводит все телефоны в базе к формату 0XXXXXXXXX'
 
    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
 
    def handle(self, *args, **options):
        dry = options['dry_run']
        changed = 0
        broken = []
 
        for model, label in ((Client, 'Client'), (User, 'User')):
            for obj in model.objects.all():
                old = obj.phone
                new = normalize_phone(old)
 
                if not new:
                    broken.append(f"{label} #{obj.id}: {old!r}")
                    continue
 
                if old != new:
                    self.stdout.write(f"{label} #{obj.id}: {old!r} → {new!r}")
                    if not dry:
                        obj.phone = new
                        obj.save(update_fields=['phone'])
                    changed += 1
 
        self.stdout.write(self.style.SUCCESS(f"Изменено: {changed}"))
 
        if broken:
            self.stdout.write(self.style.WARNING(
                f"Не удалось разобрать ({len(broken)}):"
            ))
            for line in broken:
                self.stdout.write(f"  {line}")