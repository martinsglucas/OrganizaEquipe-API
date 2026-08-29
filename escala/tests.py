from types import SimpleNamespace
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from firebase_admin import messaging
from rest_framework import status
from rest_framework.test import APIClient

from escala.admin import PushSubscriptionAdmin
from escala.models import (
    Organization,
    PushSubscription,
    Role,
    Schedule,
    Team,
    TeamJoinRequest,
    User,
)


USER_GROUP_PERMISSION_CODENAMES = {
    f"{action}_{model}"
    for model in (
        "organization",
        "team",
        "role",
        "unavailability",
        "schedule",
        "scheduleparticipation",
        "teaminvitation",
        "organizationinvitation",
        "request",
        "user",
    )
    for action in ("add", "change", "delete", "view")
} - {"add_organization"}


class DefaultUsersGroupTests(TestCase):
    def test_test_database_bootstrap_creates_group_with_expected_permissions(self):
        group = Group.objects.get(name="Users")

        self.assertSetEqual(
            set(group.permissions.values_list("codename", flat=True)),
            USER_GROUP_PERMISSION_CODENAMES,
        )

    def test_new_user_is_added_to_default_group(self):
        user = User.objects.create_user(
            email="group-member@example.com",
            password="test-password",
            first_name="Group Member",
        )

        self.assertTrue(user.groups.filter(name="Users").exists())

    def test_permission_synchronization_restores_group_idempotently(self):
        from escala.signals import synchronize_default_users_group

        Group.objects.filter(name__in=["Users", "Organization Creators"]).delete()

        synchronize_default_users_group(sender=None, using="default")
        synchronize_default_users_group(sender=None, using="default")

        group = Group.objects.get(name="Users")
        creator_group = Group.objects.get(name="Organization Creators")
        self.assertSetEqual(
            set(group.permissions.values_list("codename", flat=True)),
            USER_GROUP_PERMISSION_CODENAMES,
        )
        self.assertEqual(
            list(creator_group.permissions.values_list("codename", flat=True)),
            ["add_organization"],
        )


class ScheduleNotificationFailureTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="schedule-admin@example.com",
            password="test-password",
            first_name="Schedule Admin",
        )
        self.participant = User.objects.create_user(
            email="participant@example.com",
            password="test-password",
            first_name="Participant",
        )
        organization = Organization.objects.create(name="Notification Organization")
        organization.members.add(self.admin, self.participant)
        self.team = Team.objects.create(name="Notification Team", organization=organization)
        self.team.admins.add(self.admin)
        self.team.members.add(self.admin, self.participant)
        self.role = Role.objects.create(name="Member", team=self.team)
        self.valid_subscription = PushSubscription.objects.create(
            user=self.participant,
            token="valid-token",
            permission=PushSubscription.PERMISSION_GRANTED,
        )
        self.invalid_subscription = PushSubscription.objects.create(
            user=self.participant,
            token="invalid-token",
            permission=PushSubscription.PERMISSION_GRANTED,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def schedule_payload(self):
        return {
            "name": "Sunday Schedule",
            "team": self.team.id,
            "date": "2026-08-09",
            "hour": "19:00:00",
            "participations": [
                {
                    "user": self.participant.id,
                    "roles": [self.role.id],
                    "confirmation": False,
                },
            ],
        }

    @patch("escala.fcm._initialize_firebase", return_value=True)
    @patch("escala.fcm.messaging.send_each_for_multicast")
    def test_schedule_creation_deactivates_only_invalid_token(
        self,
        send_each_for_multicast,
        _initialize_firebase,
    ):
        def send_response(message):
            responses = [
                messaging.SendResponse(
                    None,
                    messaging.UnregisteredError("unregistered"),
                )
                if token == self.invalid_subscription.token
                else messaging.SendResponse({"name": f"messages/{index}"}, None)
                for index, token in enumerate(message.tokens, start=1)
            ]
            return SimpleNamespace(
                success_count=sum(response.success for response in responses),
                failure_count=sum(not response.success for response in responses),
                responses=responses,
            )

        send_each_for_multicast.side_effect = send_response

        response = self.client.post("/api/schedules/", self.schedule_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Schedule.objects.count(), 1)
        self.valid_subscription.refresh_from_db()
        self.invalid_subscription.refresh_from_db()
        self.assertTrue(self.valid_subscription.is_active)
        self.assertFalse(self.invalid_subscription.is_active)

    @patch("escala.fcm._initialize_firebase", return_value=True)
    @patch(
        "escala.fcm.messaging.send_each_for_multicast",
        side_effect=RuntimeError("FCM unavailable"),
    )
    def test_schedule_creation_succeeds_when_multicast_send_fails(
        self,
        send_each_for_multicast,
        _initialize_firebase,
    ):
        response = self.client.post("/api/schedules/", self.schedule_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Schedule.objects.count(), 1)
        self.valid_subscription.refresh_from_db()
        self.invalid_subscription.refresh_from_db()
        self.assertTrue(self.valid_subscription.is_active)
        self.assertTrue(self.invalid_subscription.is_active)


class PushSubscriptionAdminTests(TestCase):
    def setUp(self):
        self.regular_staff = User.objects.create_user(
            email="staff@example.com",
            password="test-password",
            first_name="Staff",
            is_staff=True,
        )
        self.superuser = User.objects.create_superuser(
            email="admin@example.com",
            password="test-password",
            first_name="Admin",
        )
        self.subscription = PushSubscription.objects.create(
            user=self.regular_staff,
            token="admin-visible-push-token",
            platform="web",
            browser="Chrome",
            device_label="Staff browser",
            permission=PushSubscription.PERMISSION_GRANTED,
        )
        self.model_admin = PushSubscriptionAdmin(PushSubscription, admin.site)

    def test_only_superuser_can_view_push_subscriptions(self):
        regular_request = type("Request", (), {"user": self.regular_staff})()
        superuser_request = type("Request", (), {"user": self.superuser})()

        self.assertFalse(self.model_admin.has_module_permission(regular_request))
        self.assertFalse(self.model_admin.has_view_permission(regular_request))
        self.assertTrue(self.model_admin.has_module_permission(superuser_request))
        self.assertTrue(self.model_admin.has_view_permission(superuser_request))

    def test_push_subscriptions_are_read_only(self):
        request = type("Request", (), {"user": self.superuser})()

        self.assertFalse(self.model_admin.has_add_permission(request))
        self.assertFalse(self.model_admin.has_change_permission(request))
        self.assertFalse(self.model_admin.has_delete_permission(request))
        self.assertIn("token", self.model_admin.get_readonly_fields(request))

    def test_regular_staff_cannot_open_push_subscription_admin_pages(self):
        self.client.force_login(self.regular_staff)

        list_response = self.client.get(
            reverse("admin:escala_pushsubscription_changelist")
        )
        detail_response = self.client.get(
            reverse(
                "admin:escala_pushsubscription_change",
                args=[self.subscription.id],
            )
        )

        self.assertEqual(list_response.status_code, 403)
        self.assertEqual(detail_response.status_code, 403)

    def test_superuser_can_view_the_complete_token_in_read_only_detail(self):
        self.client.force_login(self.superuser)

        response = self.client.get(
            reverse(
                "admin:escala_pushsubscription_change",
                args=[self.subscription.id],
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.subscription.token)
        self.assertNotContains(response, 'name="token"')


class TeamJoinRequestApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="member@example.com",
            password="test-password",
            first_name="Member",
        )
        self.team_admin = User.objects.create_user(
            email="team-admin@example.com",
            password="test-password",
            first_name="Team Admin",
        )
        self.outsider = User.objects.create_user(
            email="outsider@example.com",
            password="test-password",
            first_name="Outsider",
        )
        self.organization = Organization.objects.create(name="Community Church")
        self.organization.members.add(self.user, self.team_admin)
        self.team = Team.objects.create(name="Worship", organization=self.organization)
        self.team.admins.add(self.team_admin)
        self.team.members.add(self.team_admin)
        self.other_organization = Organization.objects.create(name="Other Church")
        self.other_organization.members.add(self.outsider)
        self.other_team = Team.objects.create(
            name="Outside Team",
            organization=self.other_organization,
        )
        self.other_team.admins.add(self.outsider)
        self.other_team.members.add(self.outsider)
        self.client = APIClient()

    def test_discovery_only_returns_teams_from_user_organizations(self):
        self.client.force_authenticate(self.user)

        response = self.client.get("/api/teams/discoverable/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([team["id"] for team in response.data], [self.team.id])

    def test_user_creates_one_pending_request_per_team(self):
        self.client.force_authenticate(self.user)

        response = self.client.post(f"/api/teams/{self.team.id}/request_join/")
        duplicate_response = self.client.post(f"/api/teams/{self.team.id}/request_join/")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], TeamJoinRequest.Status.PENDING)
        self.assertEqual(response.data["team"]["id"], self.team.id)
        self.assertEqual(duplicate_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            TeamJoinRequest.objects.filter(
                user=self.user,
                team=self.team,
                status=TeamJoinRequest.Status.PENDING,
            ).count(),
            1,
        )

    def test_user_cannot_request_team_outside_their_organizations(self):
        self.client.force_authenticate(self.user)

        response = self.client.post(f"/api/teams/{self.other_team.id}/request_join/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(TeamJoinRequest.objects.filter(user=self.user).exists())

    def test_team_admin_can_list_and_approve_request(self):
        join_request = TeamJoinRequest.objects.create(user=self.user, team=self.team)
        self.client.force_authenticate(self.team_admin)

        list_response = self.client.get(f"/api/teams/{self.team.id}/join_requests/")
        approve_response = self.client.post(
            f"/api/teams/{self.team.id}/join_requests/{join_request.id}/approve/",
        )

        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in list_response.data], [join_request.id])
        self.assertEqual(approve_response.status_code, status.HTTP_200_OK)
        join_request.refresh_from_db()
        self.assertEqual(join_request.status, TeamJoinRequest.Status.APPROVED)
        self.assertTrue(self.team.members.filter(id=self.user.id).exists())

    def test_team_admin_can_reject_without_adding_member(self):
        join_request = TeamJoinRequest.objects.create(user=self.user, team=self.team)
        self.client.force_authenticate(self.team_admin)

        response = self.client.post(
            f"/api/teams/{self.team.id}/join_requests/{join_request.id}/reject/",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        join_request.refresh_from_db()
        self.assertEqual(join_request.status, TeamJoinRequest.Status.REJECTED)
        self.assertFalse(self.team.members.filter(id=self.user.id).exists())

    def test_non_admin_cannot_review_team_requests(self):
        join_request = TeamJoinRequest.objects.create(user=self.user, team=self.team)
        self.client.force_authenticate(self.outsider)

        response = self.client.post(
            f"/api/teams/{self.team.id}/join_requests/{join_request.id}/approve/",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(self.team.members.filter(id=self.user.id).exists())

    def test_user_lists_their_request_statuses_only(self):
        own_request = TeamJoinRequest.objects.create(user=self.user, team=self.team)
        TeamJoinRequest.objects.create(user=self.outsider, team=self.other_team)
        self.client.force_authenticate(self.user)

        response = self.client.get("/api/teams/my_join_requests/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in response.data], [own_request.id])
        self.assertEqual(response.data[0]["status"], TeamJoinRequest.Status.PENDING)
