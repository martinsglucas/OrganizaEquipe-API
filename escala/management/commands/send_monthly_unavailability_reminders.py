from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from escala.fcm import send_unavailability_reminder_notification
from escala.models import MonthlyUnavailabilityReminder, PushSubscription, User


class Command(BaseCommand):
    help = "Envia o lembrete mensal para registro de indisponibilidades."

    def handle(self, *args, **options):
        now = timezone.localtime(timezone.now())
        if now.day != 1:
            self.stdout.write("Nenhum lembrete: hoje não é o primeiro dia do mês.")
            return

        month = now.date().replace(day=1)
        users = (
            User.objects.filter(is_active=True)
            .filter(Q(teams__isnull=False) | Q(administered_teams__isnull=False))
            .distinct()
            .order_by("id")
        )

        sent = 0
        already_attempted = 0
        without_tokens = 0

        for user in users:
            tokens = list(
                PushSubscription.objects.filter(
                    user=user,
                    is_active=True,
                    permission=PushSubscription.PERMISSION_GRANTED,
                )
                .values_list("token", flat=True)
                .distinct()
            )
            if not tokens:
                without_tokens += 1
                continue

            _reminder, created = MonthlyUnavailabilityReminder.objects.get_or_create(
                user=user,
                month=month,
            )
            if not created:
                already_attempted += 1
                continue

            result = send_unavailability_reminder_notification(
                fcm_tokens=tokens,
                month=month,
            )
            if result["invalid_tokens"]:
                PushSubscription.objects.filter(
                    token__in=result["invalid_tokens"]
                ).update(is_active=False)
            sent += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Lembretes mensais processados: "
                f"enviados={sent}, "
                f"já_tentados={already_attempted}, "
                f"sem_token={without_tokens}"
            )
        )
