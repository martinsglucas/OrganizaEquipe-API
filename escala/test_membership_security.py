from unittest.mock import patch

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from escala.models import (
    Organization,
    OrganizationInvitation,
    Team,
    TeamInvitation,
    User,
)


class MembershipAndInvitationSecurityTests(TestCase):
    def setUp(self):
        self.organization_admin = self.create_user(
            "organization-admin@example.com",
            "Organization Admin",
        )
        self.team_admin = self.create_user("team-admin@example.com", "Team Admin")
        self.recipient = self.create_user("recipient@example.com", "Recipient")
        self.other_recipient = self.create_user("other@example.com", "Other")
        self.outsider = self.create_user("outsider@example.com", "Outsider")

        self.organization = Organization.objects.create(name="Secure Organization")
        self.organization.admins.add(self.organization_admin)
        self.organization.members.add(self.organization_admin, self.team_admin, self.recipient)
        self.team = Team.objects.create(
            name="Secure Team",
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

    def create_organization_invitation(self, recipient=None):
        recipient = recipient or self.recipient
        return OrganizationInvitation.objects.create(
            recipient_email=recipient.email,
            organization=self.organization,
            sender_name=self.organization_admin.first_name,
        )

    def create_team_invitation(self, recipient=None):
        recipient = recipient or self.recipient
        return TeamInvitation.objects.create(
            recipient_email=recipient.email,
            team=self.team,
            sender_name=self.team_admin.first_name,
        )

    def test_only_target_admin_can_create_invitations(self):
        organization_payload = {
            "recipient_email": self.other_recipient.email,
            "organization": self.organization.id,
            "sender_name": "Spoofed sender",
        }
        team_payload = {
            "recipient_email": self.recipient.email,
            "team": self.team.id,
            "sender_name": "Spoofed sender",
        }

        self.authenticate(self.outsider)
        organization_denied = self.client.post(
            "/api/organization_invitations/",
            organization_payload,
            format="json",
        )
        team_denied = self.client.post(
            "/api/team_invitations/",
            team_payload,
            format="json",
        )

        self.assertEqual(organization_denied.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(team_denied.status_code, status.HTTP_403_FORBIDDEN)

        self.authenticate(self.organization_admin)
        organization_created = self.client.post(
            "/api/organization_invitations/",
            organization_payload,
            format="json",
        )
        self.authenticate(self.team_admin)
        team_created = self.client.post(
            "/api/team_invitations/",
            team_payload,
            format="json",
        )

        self.assertEqual(organization_created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(team_created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            OrganizationInvitation.objects.get().sender_name,
            self.organization_admin.first_name,
        )
        self.assertEqual(
            TeamInvitation.objects.get().sender_name,
            self.team_admin.first_name,
        )

    def test_invitation_lists_ignore_requested_email_and_only_return_the_recipient(self):
        own_organization_invitation = self.create_organization_invitation()
        self.create_organization_invitation(self.other_recipient)
        own_team_invitation = self.create_team_invitation()

        self.authenticate(self.recipient)
        organization_response = self.client.get(
            f"/api/organization_invitations/?addressee={self.other_recipient.email}"
        )
        team_response = self.client.get(
            f"/api/team_invitations/?addressee={self.other_recipient.email}"
        )

        self.assertEqual(organization_response.status_code, status.HTTP_200_OK)
        self.assertEqual(team_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item["id"] for item in organization_response.data],
            [own_organization_invitation.id],
        )
        self.assertEqual(
            [item["id"] for item in team_response.data],
            [own_team_invitation.id],
        )

    def test_user_invitation_action_rejects_access_to_another_users_invitations(self):
        self.create_organization_invitation(self.other_recipient)
        self.authenticate(self.recipient)

        response = self.client.get(
            f"/api/users/{self.other_recipient.id}/get_invitations/"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unrelated_user_cannot_retrieve_or_mutate_an_invitation(self):
        invitation = self.create_organization_invitation()
        self.authenticate(self.outsider)

        retrieve_response = self.client.get(
            f"/api/organization_invitations/{invitation.id}/"
        )
        accept_response = self.client.post(
            f"/api/organization_invitations/{invitation.id}/accept/"
        )
        reject_response = self.client.post(
            f"/api/organization_invitations/{invitation.id}/reject/"
        )

        self.assertEqual(retrieve_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(accept_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(reject_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(OrganizationInvitation.objects.filter(id=invitation.id).exists())

    def test_anonymous_user_cannot_inspect_or_mutate_invitations(self):
        invitation = self.create_team_invitation()

        list_response = self.client.get("/api/team_invitations/")
        accept_response = self.client.post(
            f"/api/team_invitations/{invitation.id}/accept/"
        )

        self.assertEqual(list_response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(accept_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_organization_acceptance_adds_membership_and_consumes_invitation(self):
        invitation = self.create_organization_invitation()
        self.organization.members.remove(self.recipient)
        self.authenticate(self.recipient)

        response = self.client.post(
            f"/api/organization_invitations/{invitation.id}/accept/"
        )
        repeated_response = self.client.post(
            f"/api/organization_invitations/{invitation.id}/accept/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(repeated_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(self.organization.members.filter(id=self.recipient.id).exists())
        self.assertFalse(OrganizationInvitation.objects.filter(id=invitation.id).exists())

    @patch(
        "escala.views.invitation_organization.OrganizationInvitation.delete",
        side_effect=RuntimeError("delete failed"),
    )
    def test_organization_acceptance_rolls_back_membership_if_consumption_fails(
        self,
        _delete,
    ):
        invitation = self.create_organization_invitation()
        self.organization.members.remove(self.recipient)
        self.authenticate(self.recipient)
        self.client.raise_request_exception = False

        response = self.client.post(
            f"/api/organization_invitations/{invitation.id}/accept/"
        )

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertFalse(self.organization.members.filter(id=self.recipient.id).exists())
        self.assertTrue(OrganizationInvitation.objects.filter(id=invitation.id).exists())

    def test_team_acceptance_requires_current_organization_membership(self):
        invitation = self.create_team_invitation()
        self.organization.members.remove(self.recipient)
        self.authenticate(self.recipient)

        response = self.client.post(
            f"/api/team_invitations/{invitation.id}/accept/"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(self.team.members.filter(id=self.recipient.id).exists())
        self.assertTrue(TeamInvitation.objects.filter(id=invitation.id).exists())

    def test_recipient_can_reject_and_only_target_admin_can_revoke(self):
        rejected_invitation = self.create_organization_invitation()
        revoked_invitation = self.create_organization_invitation(self.other_recipient)

        self.authenticate(self.recipient)
        reject_response = self.client.post(
            f"/api/organization_invitations/{rejected_invitation.id}/reject/"
        )
        revoke_denied = self.client.post(
            f"/api/organization_invitations/{revoked_invitation.id}/revoke/"
        )

        self.authenticate(self.organization_admin)
        revoke_response = self.client.post(
            f"/api/organization_invitations/{revoked_invitation.id}/revoke/"
        )

        self.assertEqual(reject_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(revoke_denied.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(revoke_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            OrganizationInvitation.objects.filter(id=rejected_invitation.id).exists()
        )
        self.assertFalse(
            OrganizationInvitation.objects.filter(id=revoked_invitation.id).exists()
        )

    def test_only_target_admin_can_add_or_remove_members_directly(self):
        self.authenticate(self.outsider)
        organization_add_denied = self.client.post(
            f"/api/organizations/{self.organization.id}/add_member/",
            {"user_id": self.other_recipient.id},
            format="json",
        )
        team_add_denied = self.client.post(
            f"/api/teams/{self.team.id}/add_member/",
            {"user_id": self.recipient.id},
            format="json",
        )

        self.assertEqual(organization_add_denied.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(team_add_denied.status_code, status.HTTP_403_FORBIDDEN)

        self.authenticate(self.organization_admin)
        organization_add = self.client.post(
            f"/api/organizations/{self.organization.id}/add_member/",
            {"user_id": self.other_recipient.id},
            format="json",
        )
        organization_remove = self.client.post(
            f"/api/organizations/{self.organization.id}/remove_member/",
            {"user_id": self.other_recipient.id},
            format="json",
        )
        self.authenticate(self.team_admin)
        team_add = self.client.post(
            f"/api/teams/{self.team.id}/add_member/",
            {"user_id": self.recipient.id},
            format="json",
        )
        team_remove = self.client.post(
            f"/api/teams/{self.team.id}/remove_member/",
            {"user_id": self.recipient.id},
            format="json",
        )

        self.assertEqual(organization_add.status_code, status.HTTP_200_OK)
        self.assertEqual(organization_remove.status_code, status.HTTP_200_OK)
        self.assertEqual(team_add.status_code, status.HTTP_200_OK)
        self.assertEqual(team_remove.status_code, status.HTTP_200_OK)

    def test_only_target_admin_can_update_target_membership_fields(self):
        organization_payload = {"members": [self.organization_admin.id, self.outsider.id]}
        team_payload = {
            "members": [self.team_admin.id, self.outsider.id],
            "admins": [self.team_admin.id],
            "roles": [],
        }

        self.authenticate(self.outsider)
        organization_denied = self.client.patch(
            f"/api/organizations/{self.organization.id}/",
            organization_payload,
            format="json",
        )
        team_denied = self.client.patch(
            f"/api/teams/{self.team.id}/",
            team_payload,
            format="json",
        )

        self.assertEqual(organization_denied.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(team_denied.status_code, status.HTTP_403_FORBIDDEN)

    def test_retrieve_targets_does_not_expose_nested_invitations(self):
        self.create_organization_invitation()
        self.create_team_invitation()
        self.authenticate(self.outsider)

        organization_response = self.client.get(
            f"/api/organizations/{self.organization.id}/"
        )
        team_response = self.client.get(f"/api/teams/{self.team.id}/")

        self.assertEqual(organization_response.status_code, status.HTTP_200_OK)
        self.assertEqual(team_response.status_code, status.HTTP_200_OK)
        self.assertNotIn("invitations", organization_response.data)
        self.assertNotIn("invitations", team_response.data)
