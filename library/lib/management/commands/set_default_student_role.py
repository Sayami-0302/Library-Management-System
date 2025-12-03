from django.core.management.base import BaseCommand

from lib.models import Reader


class Command(BaseCommand):
    help = "Set is_staff_member=False for all existing readers (default role = student)."

    def handle(self, *args, **options):
        total = Reader.objects.count()
        staff_count = Reader.objects.filter(is_staff_member=True).count()
        self.stdout.write(f"Total readers: {total}, currently marked staff: {staff_count}")

        # Update all readers to student (is_staff_member=False)
        updated = Reader.objects.update(is_staff_member=False)

        new_staff_count = Reader.objects.filter(is_staff_member=True).count()
        self.stdout.write(self.style.SUCCESS(
            f"Updated {updated} reader rows to is_staff_member=False. Staff count is now: {new_staff_count}"
        ))
