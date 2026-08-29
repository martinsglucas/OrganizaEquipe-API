from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from django.test import TestCase

from escala.models import Organization, Role, Team, TeamJoinRequest, User


class TeamHubApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='member@example.com',
            password='test-password',
            first_name='Member',
        )
        self.reviewer = User.objects.create_user(
            email='reviewer@example.com',
            password='test-password',
            first_name='Reviewer',
        )
        self.other_user = User.objects.create_user(
            email='other@example.com',
            password='test-password',
            first_name='Other',
        )
        self.organization = Organization.objects.create(name='Member Organization')
        self.organization.members.add(self.user, self.reviewer)
        self.other_organization = Organization.objects.create(
            name='Other Organization'
        )
        self.other_organization.members.add(self.other_user)
        self.client = APIClient()

    def create_team(
        self,
        name,
        *,
        organization=None,
        visibility=Team.Visibility.DISCOVERABLE,
        member=False,
    ):
        team = Team.objects.create(
            name=name,
            organization=organization or self.organization,
            visibility=visibility,
        )
        team.admins.add(self.reviewer)
        if member:
            team.members.add(self.user)
        return team

    def authenticate(self):
        self.client.force_authenticate(self.user)

    def test_hub_returns_member_teams_with_legacy_list_shape(self):
        member_team = self.create_team(
            'Member Team',
            visibility=Team.Visibility.PRIVATE,
            member=True,
        )
        Role.objects.create(name='Singer', team=member_team)
        self.authenticate()

        legacy = self.client.get('/api/teams/', {'userOnly': 'true'})
        response = self.client.get('/api/teams/hub/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            set(response.data),
            {'member_teams', 'discoverable_teams', 'join_requests'},
        )
        self.assertEqual(response.data['member_teams'], legacy.data)
        self.assertEqual(
            set(response.data['member_teams'][0]),
            {'id', 'name', 'code_access', 'admins', 'roles', 'members', 'visibility'},
        )
        self.assertEqual(
            response.data['member_teams'][0]['visibility'],
            Team.Visibility.PRIVATE,
        )

    def test_hub_returns_independent_empty_arrays(self):
        isolated_user = User.objects.create_user(
            email='isolated@example.com',
            password='test-password',
            first_name='Isolated',
        )
        self.client.force_authenticate(isolated_user)

        response = self.client.get('/api/teams/hub/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data,
            {
                'member_teams': [],
                'discoverable_teams': [],
                'join_requests': [],
            },
        )

    def test_discoverable_section_respects_scope_visibility_membership_and_pending(self):
        eligible = self.create_team('Eligible')
        approved_history = self.create_team('Approved History')
        private = self.create_team('Private', visibility=Team.Visibility.PRIVATE)
        closed = self.create_team('Closed', visibility=Team.Visibility.CLOSED)
        existing_member = self.create_team('Existing Member', member=True)
        pending = self.create_team('Pending')
        outside = self.create_team(
            'Outside',
            organization=self.other_organization,
        )
        TeamJoinRequest.objects.create(user=self.user, team=pending)
        TeamJoinRequest.objects.create(
            user=self.user,
            team=approved_history,
            status=TeamJoinRequest.Status.APPROVED,
            reviewed_by=self.reviewer,
            reviewed_at=timezone.now(),
        )
        self.authenticate()

        response = self.client.get('/api/teams/hub/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [team['id'] for team in response.data['discoverable_teams']],
            [approved_history.id, eligible.id],
        )
        returned_ids = {
            team['id'] for team in response.data['discoverable_teams']
        }
        self.assertNotIn(private.id, returned_ids)
        self.assertNotIn(closed.id, returned_ids)
        self.assertNotIn(existing_member.id, returned_ids)
        self.assertNotIn(pending.id, returned_ids)
        self.assertNotIn(outside.id, returned_ids)

    def test_join_requests_returns_only_authenticated_user_history(self):
        pending_team = self.create_team('Pending History')
        approved_team = self.create_team('Approved History')
        rejected_team = self.create_team('Rejected History')
        pending = TeamJoinRequest.objects.create(user=self.user, team=pending_team)
        approved = TeamJoinRequest.objects.create(
            user=self.user,
            team=approved_team,
            status=TeamJoinRequest.Status.APPROVED,
            reviewed_by=self.reviewer,
            reviewed_at=timezone.now(),
        )
        rejected = TeamJoinRequest.objects.create(
            user=self.user,
            team=rejected_team,
            status=TeamJoinRequest.Status.REJECTED,
            reviewed_by=self.reviewer,
            reviewed_at=timezone.now(),
        )
        TeamJoinRequest.objects.create(user=self.other_user, team=rejected_team)
        self.authenticate()

        response = self.client.get('/api/teams/hub/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            {item['id'] for item in response.data['join_requests']},
            {pending.id, approved.id, rejected.id},
        )
        self.assertEqual(
            {item['status'] for item in response.data['join_requests']},
            {
                TeamJoinRequest.Status.PENDING,
                TeamJoinRequest.Status.APPROVED,
                TeamJoinRequest.Status.REJECTED,
            },
        )
        reviewed_items = [
            item
            for item in response.data['join_requests']
            if item['status'] != TeamJoinRequest.Status.PENDING
        ]
        self.assertTrue(
            all(item['reviewed_by']['id'] == self.reviewer.id for item in reviewed_items)
        )

    def test_anonymous_user_cannot_open_hub(self):
        response = self.client.get('/api/teams/hub/')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
