from datetime import datetime, timedelta
from io import StringIO
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from escala.models import (
    Organization,
    PushSubscription,
    Schedule,
    ScheduleConfirmationReminder,
    ScheduleParticipation,
    Team,
    User,
)


NOW = datetime(2026, 8, 2, 12, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))


class ReminderWindowTests(SimpleTestCase):
    def test_selects_only_the_current_reminder_window(self):
        from escala.management.commands.send_schedule_confirmation_reminders import (
            get_reminder_window,
        )

        cases = {
            72: 72,
            60: 72,
            48: 48,
            36: 48,
            24: 24,
            12: 24,
            72.1: None,
            0: None,
            -1: None,
        }

        for hours_until_schedule, expected_window in cases.items():
            with self.subTest(hours_until_schedule=hours_until_schedule):
                self.assertEqual(
                    get_reminder_window(hours_until_schedule),
                    expected_window,
                )


class ScheduleConfirmationReminderCommandTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="reminder-member@example.com",
            password="test-password",
            first_name="Reminder Member",
        )
        self.user_without_token = User.objects.create_user(
            email="without-token@example.com",
            password="test-password",
            first_name="Without Token",
        )
        organization = Organization.objects.create(name="Reminder Organization")
        organization.members.add(self.user, self.user_without_token)
        self.team = Team.objects.create(name="Reminder Team", organization=organization)
        self.team.members.add(self.user, self.user_without_token)
        self.subscription = PushSubscription.objects.create(
            user=self.user,
            token="reminder-token",
            permission=PushSubscription.PERMISSION_GRANTED,
        )

    def create_participation(self, hours_until_schedule, confirmation=False, user=None):
        schedule_at = NOW + timedelta(hours=hours_until_schedule)
        schedule = Schedule.objects.create(
            name=f"Schedule {hours_until_schedule}",
            team=self.team,
            date=schedule_at.date(),
            hour=schedule_at.time().replace(tzinfo=None),
        )
        return ScheduleParticipation.objects.create(
            schedule=schedule,
            user=user or self.user,
            confirmation=confirmation,
        )

    @patch(
        "escala.management.commands.send_schedule_confirmation_reminders.send_confirmation_reminder_notification"
    )
    @patch(
        "escala.management.commands.send_schedule_confirmation_reminders.timezone.now",
        return_value=NOW,
    )
    def test_sends_72_48_and_24_hour_reminders_only_to_unconfirmed_participations(
        self,
        _now,
        send_notification,
    ):
        send_notification.return_value = {
            "invalid_tokens": [],
            "success_count": 1,
            "failure_count": 0,
        }
        for hours in (72, 48, 24):
            self.create_participation(hours)
        self.create_participation(24, confirmation=True)
        self.create_participation(80)
        self.create_participation(-1)

        call_command("send_schedule_confirmation_reminders", stdout=StringIO())

        self.assertEqual(send_notification.call_count, 3)
        self.assertSetEqual(
            {
                call.kwargs["window_hours"]
                for call in send_notification.call_args_list
            },
            {72, 48, 24},
        )
        self.assertEqual(ScheduleConfirmationReminder.objects.count(), 3)

    @patch(
        "escala.management.commands.send_schedule_confirmation_reminders.send_confirmation_reminder_notification"
    )
    @patch(
        "escala.management.commands.send_schedule_confirmation_reminders.timezone.now",
        return_value=NOW,
    )
    def test_does_not_send_the_same_participation_window_twice(
        self,
        _now,
        send_notification,
    ):
        send_notification.return_value = {
            "invalid_tokens": [],
            "success_count": 0,
            "failure_count": 1,
        }
        self.create_participation(48)

        call_command("send_schedule_confirmation_reminders", stdout=StringIO())
        call_command("send_schedule_confirmation_reminders", stdout=StringIO())

        send_notification.assert_called_once()
        self.assertEqual(ScheduleConfirmationReminder.objects.count(), 1)

    @patch(
        "escala.management.commands.send_schedule_confirmation_reminders.send_confirmation_reminder_notification"
    )
    @patch(
        "escala.management.commands.send_schedule_confirmation_reminders.timezone.now",
        return_value=NOW,
    )
    def test_skips_users_without_active_subscriptions(
        self,
        _now,
        send_notification,
    ):
        self.create_participation(24, user=self.user_without_token)

        call_command("send_schedule_confirmation_reminders", stdout=StringIO())

        send_notification.assert_not_called()
        self.assertFalse(ScheduleConfirmationReminder.objects.exists())

    @patch(
        "escala.management.commands.send_schedule_confirmation_reminders.send_confirmation_reminder_notification"
    )
    @patch(
        "escala.management.commands.send_schedule_confirmation_reminders.timezone.now",
        return_value=NOW,
    )
    def test_deactivates_invalid_tokens_returned_by_fcm(
        self,
        _now,
        send_notification,
    ):
        send_notification.return_value = {
            "invalid_tokens": [self.subscription.token],
            "success_count": 0,
            "failure_count": 1,
        }
        self.create_participation(24)

        call_command("send_schedule_confirmation_reminders", stdout=StringIO())

        self.subscription.refresh_from_db()
        self.assertFalse(self.subscription.is_active)
