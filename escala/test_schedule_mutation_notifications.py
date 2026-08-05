from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from rest_framework import status
from rest_framework.test import APIClient

from escala.fcm import (
    send_schedule_deleted_notification,
    send_schedule_notification,
    send_schedule_updated_notification,
)
from escala.models import (
    Organization,
    PushSubscription,
    Role,
    Schedule,
    ScheduleParticipation,
    Team,
    User,
)


class ScheduleMutationNotificationPayloadTests(SimpleTestCase):
    @patch("escala.fcm._send_multicast_notification")
    def test_creation_payload_links_to_the_schedule_detail(self, send_multicast):
        send_multicast.return_value = {"invalid_tokens": []}

        send_schedule_notification(
            fcm_tokens=["token"],
            schedule_id=17,
            schedule_name="Sunday Schedule",
            schedule_date=self._date(),
            schedule_hour=self._hour(),
        )

        self.assertEqual(send_multicast.call_args.kwargs["data"]["type"], "new_schedule")
        self.assertEqual(send_multicast.call_args.kwargs["data"]["schedule_id"], "17")
        self.assertEqual(
            send_multicast.call_args.kwargs["link"],
            "https://organizaequipe.onrender.com/escala/17",
        )

    @patch("escala.fcm._send_multicast_notification")
    def test_update_payload_distinguishes_removed_participants(self, send_multicast):
        send_multicast.return_value = {"invalid_tokens": []}

        send_schedule_updated_notification(
            fcm_tokens=["token"],
            schedule_id=17,
            schedule_name="Updated Schedule",
            schedule_date=self._date(),
            schedule_hour=self._hour(),
            participant_removed=True,
        )

        data = send_multicast.call_args.kwargs["data"]
        self.assertEqual(data["type"], "updated_schedule")
        self.assertEqual(data["schedule_id"], "17")
        self.assertEqual(data["participant_removed"], "true")
        self.assertEqual(
            send_multicast.call_args.kwargs["link"],
            "https://organizaequipe.onrender.com/escala/17",
        )

    @patch("escala.fcm._send_multicast_notification")
    def test_deletion_payload_links_to_the_schedule_list(self, send_multicast):
        send_multicast.return_value = {"invalid_tokens": []}

        send_schedule_deleted_notification(
            fcm_tokens=["token"],
            schedule_id=17,
            schedule_name="Cancelled Schedule",
            schedule_date=self._date(),
            schedule_hour=self._hour(),
        )

        data = send_multicast.call_args.kwargs["data"]
        self.assertEqual(data["type"], "deleted_schedule")
        self.assertEqual(data["schedule_id"], "17")
        self.assertEqual(
            send_multicast.call_args.kwargs["link"],
            "https://organizaequipe.onrender.com/escala",
        )

    @staticmethod
    def _date():
        from datetime import date

        return date(2026, 8, 9)

    @staticmethod
    def _hour():
        from datetime import time

        return time(19, 0)


class ScheduleMutationNotificationApiTests(TestCase):
    def setUp(self):
        self.admin = self.create_user("admin@example.com", "Admin")
        self.current_participant = self.create_user("current@example.com", "Current")
        self.removed_participant = self.create_user("removed@example.com", "Removed")
        self.without_subscription = self.create_user("without@example.com", "Without")

        organization = Organization.objects.create(name="Mutation Organization")
        organization.members.add(
            self.admin,
            self.current_participant,
            self.removed_participant,
            self.without_subscription,
        )
        self.team = Team.objects.create(name="Mutation Team", organization=organization)
        self.team.admins.add(self.admin)
        self.team.members.add(
            self.admin,
            self.current_participant,
            self.removed_participant,
            self.without_subscription,
        )
        self.role = Role.objects.create(name="Member", team=self.team)
        self.current_subscription = self.create_subscription(
            self.current_participant,
            "current-token",
        )
        self.removed_subscription = self.create_subscription(
            self.removed_participant,
            "removed-token",
        )
        self.schedule = Schedule.objects.create(
            name="Original Schedule",
            team=self.team,
            date="2026-08-09",
            hour="19:00:00",
        )
        self.add_participation(self.current_participant)
        self.add_participation(self.removed_participant)

        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def create_user(self, email, first_name):
        return User.objects.create_user(
            email=email,
            password="test-password",
            first_name=first_name,
        )

    def create_subscription(self, user, token):
        return PushSubscription.objects.create(
            user=user,
            token=token,
            permission=PushSubscription.PERMISSION_GRANTED,
        )

    def add_participation(self, user):
        participation = ScheduleParticipation.objects.create(
            schedule=self.schedule,
            user=user,
            confirmation=False,
        )
        participation.roles.add(self.role)
        return participation

    def update_payload(self, participants=None):
        participants = participants or [self.current_participant]
        return {
            "name": "Updated Schedule",
            "team": self.team.id,
            "date": "2026-08-10",
            "hour": "20:30:00",
            "participations": [
                {
                    "user": participant.id,
                    "roles": [self.role.id],
                    "confirmation": False,
                }
                for participant in participants
            ],
        }

    @patch("escala.views.schedule.send_schedule_updated_notification")
    def test_edit_notifies_current_and_removed_participants(self, send_notification):
        send_notification.return_value = []

        response = self.client.put(
            f"/api/schedules/{self.schedule.id}/",
            self.update_payload(),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.schedule.refresh_from_db()
        self.assertEqual(self.schedule.name, "Updated Schedule")
        self.assertEqual(send_notification.call_count, 2)
        calls_by_removed = {
            call.kwargs["participant_removed"]: call.kwargs
            for call in send_notification.call_args_list
        }
        self.assertEqual(calls_by_removed[False]["fcm_tokens"], ["current-token"])
        self.assertEqual(calls_by_removed[True]["fcm_tokens"], ["removed-token"])
        self.assertEqual(calls_by_removed[False]["schedule_name"], "Updated Schedule")

    @patch("escala.views.schedule.send_schedule_updated_notification")
    def test_edit_deactivates_invalid_tokens(self, send_notification):
        def notification_result(fcm_tokens, **kwargs):
            return ["removed-token"] if "removed-token" in fcm_tokens else []

        send_notification.side_effect = notification_result

        response = self.client.put(
            f"/api/schedules/{self.schedule.id}/",
            self.update_payload(),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.current_subscription.refresh_from_db()
        self.removed_subscription.refresh_from_db()
        self.assertTrue(self.current_subscription.is_active)
        self.assertFalse(self.removed_subscription.is_active)

    @patch("escala.views.schedule.send_schedule_updated_notification")
    def test_edit_skips_notification_when_no_participant_has_a_subscription(
        self,
        send_notification,
    ):
        self.current_subscription.is_active = False
        self.current_subscription.save(update_fields=["is_active"])
        self.removed_subscription.is_active = False
        self.removed_subscription.save(update_fields=["is_active"])

        response = self.client.put(
            f"/api/schedules/{self.schedule.id}/",
            self.update_payload([self.without_subscription]),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        send_notification.assert_not_called()

    @patch("escala.views.schedule.send_schedule_deleted_notification")
    def test_delete_notifies_participants_captured_before_deletion(
        self,
        send_notification,
    ):
        send_notification.return_value = []
        schedule_id = self.schedule.id

        response = self.client.delete(f"/api/schedules/{schedule_id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Schedule.objects.filter(id=schedule_id).exists())
        self.assertCountEqual(
            send_notification.call_args.kwargs["fcm_tokens"],
            ["current-token", "removed-token"],
        )
        self.assertEqual(send_notification.call_args.kwargs["schedule_id"], schedule_id)

    @patch("escala.fcm._initialize_firebase", return_value=True)
    @patch(
        "escala.fcm.messaging.send_each_for_multicast",
        side_effect=RuntimeError("FCM unavailable"),
    )
    def test_delete_succeeds_when_multicast_send_fails(
        self,
        send_each_for_multicast,
        _initialize_firebase,
    ):
        schedule_id = self.schedule.id

        response = self.client.delete(f"/api/schedules/{schedule_id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Schedule.objects.filter(id=schedule_id).exists())
