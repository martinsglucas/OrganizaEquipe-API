from datetime import datetime

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from escala.fcm import send_confirmation_reminder_notification
from escala.models import (
    PushSubscription,
    ScheduleConfirmationReminder,
    ScheduleParticipation,
)


REMINDER_WINDOWS = (24, 48, 72)


def get_reminder_window(hours_until_schedule):
    if hours_until_schedule <= 0:
        return None

    return next(
        (window for window in REMINDER_WINDOWS if hours_until_schedule <= window),
        None,
    )


class Command(BaseCommand):
    help = "Envia lembretes de confirmação para participações em escalas futuras."

    def handle(self, *args, **options):
        current_timezone = timezone.get_current_timezone()
        now = timezone.localtime(timezone.now(), current_timezone)
        participations = (
            ScheduleParticipation.objects.filter(
                Q(confirmation=False) | Q(confirmation__isnull=True),
                schedule__date__gte=now.date(),
            )
            .select_related("schedule", "user")
            .order_by("schedule__date", "schedule__hour", "id")
        )

        sent = 0
        already_attempted = 0
        without_tokens = 0

        for participation in participations:
            schedule = participation.schedule
            schedule_at = timezone.make_aware(
                datetime.combine(schedule.date, schedule.hour),
                current_timezone,
            )
            hours_until_schedule = (schedule_at - now).total_seconds() / 3600
            window_hours = get_reminder_window(hours_until_schedule)
            if window_hours is None:
                continue

            tokens = list(
                PushSubscription.objects.filter(
                    user=participation.user,
                    is_active=True,
                    permission=PushSubscription.PERMISSION_GRANTED,
                )
                .values_list("token", flat=True)
                .distinct()
            )
            if not tokens:
                without_tokens += 1
                continue

            _reminder, created = ScheduleConfirmationReminder.objects.get_or_create(
                participation=participation,
                window_hours=window_hours,
            )
            if not created:
                already_attempted += 1
                continue

            result = send_confirmation_reminder_notification(
                fcm_tokens=tokens,
                schedule_id=schedule.id,
                schedule_name=schedule.name,
                schedule_date=schedule.date,
                schedule_hour=schedule.hour,
                window_hours=window_hours,
            )
            if result["invalid_tokens"]:
                PushSubscription.objects.filter(
                    token__in=result["invalid_tokens"]
                ).update(is_active=False)
            sent += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Lembretes processados: "
                f"enviados={sent}, "
                f"já_tentados={already_attempted}, "
                f"sem_token={without_tokens}"
            )
        )
