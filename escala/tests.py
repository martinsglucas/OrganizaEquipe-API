from django.contrib import admin
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from escala.admin import OrganizationCreationRequestAdmin
from escala.models import Organization, OrganizationCreationRequest, Team, TeamJoinRequest, User


class OrganizationCreationRequestApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="member@example.com",
            password="test-password",
            first_name="Member",
        )
        self.superuser = User.objects.create_superuser(
            email="admin@example.com",
            password="test-password",
            first_name="Admin",
        )
        self.client = APIClient()

    def test_regular_user_creates_request_instead_of_organization(self):
        self.client.force_authenticate(self.user)

        response = self.client.post(
            "/api/organization_requests/",
            {"name": "Community Church"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], OrganizationCreationRequest.Status.PENDING)
        self.assertEqual(response.data["requester"], self.user.id)
        self.assertFalse(Organization.objects.filter(name="Community Church").exists())

    def test_regular_user_cannot_create_organization_directly(self):
        self.client.force_authenticate(self.user)

        response = self.client.post(
            "/api/organizations/",
            {"name": "Bypass", "admins": [self.user.id], "members": [self.user.id]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Organization.objects.filter(name="Bypass").exists())

    def test_user_only_lists_their_own_requests(self):
        own_request = OrganizationCreationRequest.objects.create(
            requester=self.user,
            name="Own request",
        )
        OrganizationCreationRequest.objects.create(
            requester=self.superuser,
            name="Other request",
        )
        self.client.force_authenticate(self.user)

        response = self.client.get("/api/organization_requests/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in response.data], [own_request.id])

    def test_duplicate_pending_request_is_rejected(self):
        OrganizationCreationRequest.objects.create(
            requester=self.user,
            name="Community Church",
        )
        self.client.force_authenticate(self.user)

        response = self.client.post(
            "/api/organization_requests/",
            {"name": "Community Church"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            OrganizationCreationRequest.objects.filter(
                requester=self.user,
                name="Community Church",
                status=OrganizationCreationRequest.Status.PENDING,
            ).count(),
            1,
        )

    def test_superuser_approval_creates_organization_and_memberships_once(self):
        creation_request = OrganizationCreationRequest.objects.create(
            requester=self.user,
            name="Community Church",
        )

        organization = creation_request.approve(self.superuser)
        repeated_organization = creation_request.approve(self.superuser)

        creation_request.refresh_from_db()
        self.assertEqual(creation_request.status, OrganizationCreationRequest.Status.APPROVED)
        self.assertEqual(creation_request.organization, organization)
        self.assertEqual(repeated_organization, organization)
        self.assertTrue(organization.admins.filter(id=self.user.id).exists())
        self.assertTrue(organization.members.filter(id=self.user.id).exists())
        self.assertEqual(Organization.objects.filter(name="Community Church").count(), 1)

    def test_rejection_preserves_status_without_creating_organization(self):
        creation_request = OrganizationCreationRequest.objects.create(
            requester=self.user,
            name="Community Church",
        )

        creation_request.reject(self.superuser)

        creation_request.refresh_from_db()
        self.assertEqual(creation_request.status, OrganizationCreationRequest.Status.REJECTED)
        self.assertIsNone(creation_request.organization)
        self.assertFalse(Organization.objects.filter(name="Community Church").exists())


class OrganizationCreationRequestAdminTests(TestCase):
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
        self.model_admin = OrganizationCreationRequestAdmin(
            OrganizationCreationRequest,
            admin.site,
        )

    def test_only_superuser_can_manage_requests_in_admin(self):
        regular_request = type("Request", (), {"user": self.regular_staff})()
        superuser_request = type("Request", (), {"user": self.superuser})()

        self.assertFalse(self.model_admin.has_module_permission(regular_request))
        self.assertFalse(self.model_admin.has_change_permission(regular_request))
        self.assertTrue(self.model_admin.has_module_permission(superuser_request))
        self.assertTrue(self.model_admin.has_change_permission(superuser_request))


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
