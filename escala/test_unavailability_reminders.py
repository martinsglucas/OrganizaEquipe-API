from datetime import date, datetime
from io import StringIO
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from escala.fcm import send_unavailability_reminder_notification
from escala.models import (
    MonthlyUnavailabilityReminder,
    Organization,
    PushSubscription,
    Team,
    User,
)


MONTH_START = datetime(2026, 8, 1, 9, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))


class UnavailabilityReminderNotificationTests(SimpleTestCase):
    @patch("escala.fcm._send_multicast_notification")
    def test_notification_links_to_unavailability_registration(self, send_multicast):
        send_unavailability_reminder_notification(
            fcm_tokens=["token"],
            month=date(2026, 8, 1),
        )

        self.assertEqual(
            send_multicast.call_args.kwargs["link"],
            "https://organizaequipe.onrender.com/indisponibilidade",
        )
        self.assertEqual(
            send_multicast.call_args.kwargs["data"]["type"],
            "monthly_unavailability_reminder",
        )


class MonthlyUnavailabilityReminderCommandTests(TestCase):
    def setUp(self):
        self.member = self.create_user("member@example.com", "Member")
        self.admin = self.create_user("admin@example.com", "Admin")
        self.inactive_member = self.create_user(
            "inactive@example.com",
            "Inactive",
            is_active=False,
        )
        self.without_token = self.create_user("without-token@example.com", "Without Token")
        self.outsider = self.create_user("outsider@example.com", "Outsider")

        organization = Organization.objects.create(name="Monthly Reminder Organization")
        organization.members.add(
            self.member,
            self.admin,
            self.inactive_member,
            self.without_token,
        )
        team = Team.objects.create(name="Monthly Reminder Team", organization=organization)
        team.members.add(self.member, self.inactive_member, self.without_token)
        team.admins.add(self.admin)
        second_team = Team.objects.create(name="Second Team", organization=organization)
        second_team.members.add(self.member)

        self.member_subscription = self.create_subscription(self.member, "member-token")
        self.admin_subscription = self.create_subscription(self.admin, "admin-token")
        self.create_subscription(self.inactive_member, "inactive-token")
        self.create_subscription(self.outsider, "outsider-token")

    def create_user(self, email, first_name, is_active=True):
        return User.objects.create_user(
            email=email,
            password="test-password",
            first_name=first_name,
            is_active=is_active,
        )

    def create_subscription(self, user, token):
        return PushSubscription.objects.create(
            user=user,
            token=token,
            permission=PushSubscription.PERMISSION_GRANTED,
        )

    @patch(
        "escala.management.commands.send_monthly_unavailability_reminders.send_unavailability_reminder_notification"
    )
    @patch(
        "escala.management.commands.send_monthly_unavailability_reminders.timezone.now",
        return_value=MONTH_START,
    )
    def test_notifies_active_members_and_admins_once_across_teams(
        self,
        _now,
        send_notification,
    ):
        send_notification.return_value = {
            "invalid_tokens": [],
            "success_count": 1,
            "failure_count": 0,
        }

        call_command("send_monthly_unavailability_reminders", stdout=StringIO())

        self.assertEqual(send_notification.call_count, 2)
        self.assertSetEqual(
            {
                call.kwargs["fcm_tokens"][0]
                for call in send_notification.call_args_list
            },
            {"member-token", "admin-token"},
        )
        self.assertEqual(MonthlyUnavailabilityReminder.objects.count(), 2)

    @patch(
        "escala.management.commands.send_monthly_unavailability_reminders.send_unavailability_reminder_notification"
    )
    @patch(
        "escala.management.commands.send_monthly_unavailability_reminders.timezone.now",
        return_value=MONTH_START,
    )
    def test_does_not_attempt_the_same_user_month_twice(
        self,
        _now,
        send_notification,
    ):
        send_notification.return_value = {
            "invalid_tokens": [],
            "success_count": 0,
            "failure_count": 1,
        }

        call_command("send_monthly_unavailability_reminders", stdout=StringIO())
        call_command("send_monthly_unavailability_reminders", stdout=StringIO())

        self.assertEqual(send_notification.call_count, 2)
        self.assertEqual(MonthlyUnavailabilityReminder.objects.count(), 2)

    @patch(
        "escala.management.commands.send_monthly_unavailability_reminders.send_unavailability_reminder_notification"
    )
    @patch(
        "escala.management.commands.send_monthly_unavailability_reminders.timezone.now",
        return_value=MONTH_START.replace(day=2),
    )
    def test_does_nothing_outside_the_first_day_of_month(
        self,
        _now,
        send_notification,
    ):
        call_command("send_monthly_unavailability_reminders", stdout=StringIO())

        send_notification.assert_not_called()
        self.assertFalse(MonthlyUnavailabilityReminder.objects.exists())

    @patch(
        "escala.management.commands.send_monthly_unavailability_reminders.send_unavailability_reminder_notification"
    )
    @patch(
        "escala.management.commands.send_monthly_unavailability_reminders.timezone.now",
        return_value=MONTH_START,
    )
    def test_deactivates_invalid_tokens_without_stopping_the_job(
        self,
        _now,
        send_notification,
    ):
        def send_result(fcm_tokens, month):
            return {
                "invalid_tokens": (
                    ["member-token"] if "member-token" in fcm_tokens else []
                ),
                "success_count": 0,
                "failure_count": 1,
            }

        send_notification.side_effect = send_result

        call_command("send_monthly_unavailability_reminders", stdout=StringIO())

        self.member_subscription.refresh_from_db()
        self.admin_subscription.refresh_from_db()
        self.assertFalse(self.member_subscription.is_active)
        self.assertTrue(self.admin_subscription.is_active)
