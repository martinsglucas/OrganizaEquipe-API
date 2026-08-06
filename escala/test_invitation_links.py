from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from escala.models import InvitationLink, Organization, Request, Team, User


class InvitationLinkLifecycleTests(TestCase):
    def setUp(self):
        self.organization_admin = self.create_user(
            "organization-admin@example.com",
            "Organization Admin",
        )
        self.team_admin = self.create_user("team-admin@example.com", "Team Admin")
        self.outsider = self.create_user("outsider@example.com", "Outsider")

        self.organization = Organization.objects.create(name="Invite Organization")
        self.organization.admins.add(self.organization_admin)
        self.organization.members.add(self.organization_admin, self.team_admin)
        self.team = Team.objects.create(
            name="Invite Team",
            organization=self.organization,
        )
        self.team.admins.add(self.team_admin)
        self.team.members.add(self.team_admin)
        self.client = APIClient()

    @staticmethod
    def create_user(email, first_name):
        return User.objects.create_user(
            email=email,
            password="test-password",
            first_name=first_name,
        )

    def authenticate(self, user):
        self.client.force_authenticate(user)

    def create_link(self, target_type="organization", target_id=None, **extra):
        if target_id is None:
            target_id = (
                self.organization.id if target_type == "organization" else self.team.id
            )
        payload = {
            "target_type": target_type,
            "target_id": target_id,
            **extra,
        }
        return self.client.post("/api/invitation_links/", payload, format="json")

    def test_target_admin_generates_and_retrieves_one_active_reusable_link(self):
        self.authenticate(self.organization_admin)

        created = self.create_link()
        repeated = self.create_link()
        listed = self.client.get(
            "/api/invitation_links/",
            {"target_type": "organization", "target_id": self.organization.id},
        )

        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(repeated.status_code, status.HTTP_200_OK)
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        self.assertEqual(created.data["token"], repeated.data["token"])
        self.assertEqual(listed.data, [created.data])
        self.assertEqual(InvitationLink.objects.count(), 1)
        self.assertEqual(created.data["status"], "active")
        self.assertIsNone(created.data["expires_at"])

    def test_team_admin_can_manage_team_link_but_other_users_cannot(self):
        self.authenticate(self.outsider)
        outsider_response = self.create_link("team")

        self.authenticate(self.organization_admin)
        wrong_admin_response = self.create_link("team")

        self.authenticate(self.team_admin)
        admin_response = self.create_link("team")

        self.assertEqual(outsider_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(wrong_admin_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(admin_response.status_code, status.HTTP_201_CREATED)

    def test_link_token_is_opaque_unique_and_absent_from_unrelated_endpoints(self):
        self.authenticate(self.organization_admin)
        organization_link = self.create_link().data
        self.authenticate(self.team_admin)
        team_link = self.create_link("team").data

        self.assertGreaterEqual(len(organization_link["token"]), 32)
        self.assertNotEqual(organization_link["token"], team_link["token"])
        self.assertNotIn(str(self.organization.id), organization_link["token"])
        self.assertNotEqual(organization_link["token"], self.organization.code_access)

        organizations = self.client.get("/api/organizations/")
        teams = self.client.get("/api/teams/")
        self.assertNotIn("token", str(organizations.data).lower())
        self.assertNotIn("token", str(teams.data).lower())

    def test_anonymous_resolution_returns_only_minimal_active_target_information(self):
        self.authenticate(self.organization_admin)
        token = self.create_link().data["token"]
        self.client.force_authenticate(user=None)

        response = self.client.get(
            "/api/invitation_links/resolve/",
            {"token": token},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data,
            {
                "target_type": "organization",
                "target_id": self.organization.id,
                "target_name": self.organization.name,
                "status": "active",
            },
        )

    def test_revocation_immediately_invalidates_token(self):
        self.authenticate(self.organization_admin)
        link = self.create_link().data

        revoked = self.client.post(f"/api/invitation_links/{link['id']}/revoke/")
        self.client.force_authenticate(user=None)
        resolution = self.client.get(
            "/api/invitation_links/resolve/",
            {"token": link["token"]},
        )

        self.assertEqual(revoked.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(resolution.status_code, status.HTTP_404_NOT_FOUND)

    def test_regeneration_invalidates_previous_token_and_is_reusable(self):
        self.authenticate(self.organization_admin)
        original = self.create_link().data

        regenerated = self.client.post(
            f"/api/invitation_links/{original['id']}/regenerate/",
            {},
            format="json",
        )
        repeated = self.create_link()
        self.client.force_authenticate(user=None)
        old_resolution = self.client.get(
            "/api/invitation_links/resolve/",
            {"token": original["token"]},
        )
        new_resolution = self.client.get(
            "/api/invitation_links/resolve/",
            {"token": regenerated.data["token"]},
        )

        self.assertEqual(regenerated.status_code, status.HTTP_200_OK)
        self.assertNotEqual(original["token"], regenerated.data["token"])
        self.assertEqual(repeated.data["token"], regenerated.data["token"])
        self.assertEqual(old_resolution.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(new_resolution.status_code, status.HTTP_200_OK)

    def test_optional_expiration_is_stored_and_enforced(self):
        expiration = timezone.now() + timedelta(days=2)
        self.authenticate(self.organization_admin)
        response = self.create_link(expires_at=expiration.isoformat())
        link = InvitationLink.objects.get(pk=response.data["id"])

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNotNone(response.data["expires_at"])
        self.assertTrue(link.is_active)

        link.expires_at = timezone.now() - timedelta(seconds=1)
        link.save(update_fields=["expires_at"])
        self.client.force_authenticate(user=None)
        expired_resolution = self.client.get(
            "/api/invitation_links/resolve/",
            {"token": link.token},
        )

        self.assertFalse(link.is_active)
        self.assertEqual(expired_resolution.status_code, status.HTTP_404_NOT_FOUND)

    def test_only_target_admin_can_revoke_or_regenerate(self):
        self.authenticate(self.organization_admin)
        link = self.create_link().data
        self.authenticate(self.outsider)

        revoke = self.client.post(f"/api/invitation_links/{link['id']}/revoke/")
        regenerate = self.client.post(
            f"/api/invitation_links/{link['id']}/regenerate/",
            {},
            format="json",
        )

        self.assertEqual(revoke.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(regenerate.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(InvitationLink.objects.get(pk=link["id"]).is_active)

    def test_invalid_target_shape_is_rejected(self):
        self.authenticate(self.organization_admin)

        invalid_type = self.create_link("unsupported")
        missing_target = self.client.post(
            "/api/invitation_links/",
            {"target_type": "organization"},
            format="json",
        )

        self.assertEqual(invalid_type.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(missing_target.status_code, status.HTTP_400_BAD_REQUEST)

    def test_authenticated_user_accepts_organization_link_without_side_effects(self):
        self.authenticate(self.organization_admin)
        link = self.create_link().data
        self.authenticate(self.outsider)

        response = self.client.post(
            "/api/invitation_links/accept/",
            {"token": link["token"]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(self.organization.members.filter(pk=self.outsider.pk).exists())
        self.assertFalse(self.organization.admins.filter(pk=self.outsider.pk).exists())
        self.assertEqual(Request.objects.count(), 0)
        self.assertTrue(InvitationLink.objects.get(pk=link["id"]).is_active)

    def test_repeated_organization_link_acceptance_is_idempotent(self):
        self.authenticate(self.organization_admin)
        token = self.create_link().data["token"]
        self.organization.members.add(self.outsider)
        self.authenticate(self.outsider)

        response = self.client.post(
            "/api/invitation_links/accept/",
            {"token": token},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            self.organization.members.filter(pk=self.outsider.pk).count(),
            1,
        )
        self.assertEqual(Request.objects.count(), 0)

    def test_invalid_or_ineligible_tokens_are_rejected_without_leaking_reason(self):
        self.authenticate(self.organization_admin)
        revoked_link = self.create_link().data
        InvitationLink.objects.filter(pk=revoked_link["id"]).update(
            revoked_at=timezone.now()
        )

        expired_organization = Organization.objects.create(name="Expired Organization")
        expired_organization.admins.add(self.organization_admin)
        expired_link = InvitationLink.objects.create(
            organization=expired_organization,
            created_by=self.organization_admin,
            expires_at=timezone.now() - timedelta(seconds=1),
        )

        self.authenticate(self.team_admin)
        team_link = self.create_link("team").data
        self.authenticate(self.outsider)

        for token in [
            revoked_link["token"],
            expired_link.token,
            team_link["token"],
            "unknown-token",
        ]:
            with self.subTest(token=token):
                response = self.client.post(
                    "/api/invitation_links/accept/",
                    {"token": token},
                    format="json",
                )

                self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        self.assertFalse(self.organization.members.filter(pk=self.outsider.pk).exists())
        self.assertFalse(
            expired_organization.members.filter(pk=self.outsider.pk).exists()
        )
        self.assertFalse(self.team.members.filter(pk=self.outsider.pk).exists())

    def test_anonymous_user_cannot_accept_organization_link(self):
        self.authenticate(self.organization_admin)
        token = self.create_link().data["token"]
        self.client.force_authenticate(user=None)

        response = self.client.post(
            "/api/invitation_links/accept/",
            {"token": token},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(self.organization.members.filter(pk=self.outsider.pk).exists())
