from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from rest_framework import status
from rest_framework.test import APIClient

from escala.models import InvitationLink, Organization, Team, TeamJoinRequest, User


class TeamVisibilityMigrationTests(TransactionTestCase):
    migrate_from = [('escala', '0010_schedule_notes')]
    migrate_to = [('escala', '0011_team_visibility')]

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state(self.migrate_from).apps
        organization = old_apps.get_model('escala', 'Organization').objects.create(
            name='Existing Organization'
        )
        self.team_id = old_apps.get_model('escala', 'Team').objects.create(
            name='Existing Team',
            organization=organization,
        ).id

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        self.apps = executor.loader.project_state(self.migrate_to).apps

    def tearDown(self):
        MigrationExecutor(connection).migrate(
            MigrationExecutor(connection).loader.graph.leaf_nodes()
        )
        super().tearDown()

    def test_existing_teams_migrate_as_discoverable(self):
        team = self.apps.get_model('escala', 'Team').objects.get(pk=self.team_id)

        self.assertEqual(team.visibility, 'discoverable')


class TeamVisibilityApiTests(TestCase):
    def setUp(self):
        self.team_admin = User.objects.create_user(
            email='team-admin@example.com',
            password='test-password',
            first_name='Team Admin',
        )
        self.member = User.objects.create_user(
            email='member@example.com',
            password='test-password',
            first_name='Member',
        )
        self.organization = Organization.objects.create(name='Community Church')
        self.organization.members.add(self.team_admin, self.member)
        self.discoverable_team = self.create_team('Discoverable Team')
        self.private_team = self.create_team('Private Team', visibility='private')
        self.closed_team = self.create_team('Closed Team', visibility='closed')
        self.client = APIClient()

    def create_team(self, name, visibility='discoverable'):
        team = Team.objects.create(
            name=name,
            organization=self.organization,
            visibility=visibility,
        )
        team.admins.add(self.team_admin)
        team.members.add(self.team_admin)
        return team

    def authenticate(self, user):
        self.client.force_authenticate(user)

    def test_default_and_team_serializers_expose_visibility(self):
        default_team = Team.objects.create(
            name='Default Team',
            organization=self.organization,
        )
        default_team.members.add(self.team_admin)
        self.authenticate(self.team_admin)

        retrieved = self.client.get(f'/api/teams/{default_team.id}/')
        listed = self.client.get('/api/teams/', {'userOnly': 'true'})
        created = self.client.post(
            '/api/teams/',
            {
                'name': 'Created Private Team',
                'organization': self.organization.id,
                'visibility': 'private',
            },
            format='json',
        )

        self.assertEqual(default_team.visibility, Team.Visibility.DISCOVERABLE)
        self.assertEqual(retrieved.data['visibility'], Team.Visibility.DISCOVERABLE)
        self.assertTrue(all('visibility' in team for team in listed.data))
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(created.data['visibility'], Team.Visibility.PRIVATE)

    def test_only_team_admin_can_change_visibility_and_invalid_value_is_rejected(self):
        self.authenticate(self.member)
        denied = self.client.patch(
            f'/api/teams/{self.discoverable_team.id}/',
            {'visibility': 'private'},
            format='json',
        )
        self.authenticate(self.team_admin)
        updated = self.client.patch(
            f'/api/teams/{self.discoverable_team.id}/',
            {'visibility': 'private'},
            format='json',
        )
        invalid = self.client.patch(
            f'/api/teams/{self.discoverable_team.id}/',
            {'visibility': 'unsupported'},
            format='json',
        )

        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(updated.status_code, status.HTTP_200_OK)
        self.assertEqual(updated.data['visibility'], Team.Visibility.PRIVATE)
        self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST)

    def test_discovery_and_code_lookup_only_return_discoverable_teams(self):
        self.authenticate(self.member)

        discovery = self.client.get('/api/teams/discoverable/')
        discoverable_code = self.client.get(
            '/api/teams/', {'codeAccess': self.discoverable_team.code_access}
        )
        private_code = self.client.get(
            '/api/teams/', {'codeAccess': self.private_team.code_access}
        )
        closed_code = self.client.get(
            '/api/teams/', {'codeAccess': self.closed_team.code_access}
        )

        self.assertEqual(
            [team['id'] for team in discovery.data],
            [self.discoverable_team.id],
        )
        self.assertEqual(
            [team['id'] for team in discoverable_code.data],
            [self.discoverable_team.id],
        )
        self.assertEqual(private_code.data, [])
        self.assertEqual(closed_code.data, [])

    def test_only_discoverable_teams_accept_join_requests(self):
        self.authenticate(self.member)

        discoverable = self.client.post(
            f'/api/teams/{self.discoverable_team.id}/request_join/'
        )
        private = self.client.post(f'/api/teams/{self.private_team.id}/request_join/')
        closed = self.client.post(f'/api/teams/{self.closed_team.id}/request_join/')

        self.assertEqual(discoverable.status_code, status.HTTP_201_CREATED)
        self.assertEqual(private.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(closed.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            TeamJoinRequest.objects.filter(user=self.member).values_list(
                'team_id', flat=True
            ).get(),
            self.discoverable_team.id,
        )


class ClosedTeamInvitationLinkTests(TestCase):
    def setUp(self):
        self.team_admin = User.objects.create_user(
            email='team-admin@example.com',
            password='test-password',
            first_name='Team Admin',
        )
        self.member = User.objects.create_user(
            email='member@example.com',
            password='test-password',
            first_name='Member',
        )
        self.organization = Organization.objects.create(name='Invite Organization')
        self.organization.members.add(self.team_admin, self.member)
        self.team = Team.objects.create(
            name='Private Team',
            organization=self.organization,
            visibility='private',
        )
        self.team.admins.add(self.team_admin)
        self.team.members.add(self.team_admin)
        self.client = APIClient()

    def authenticate(self, user):
        self.client.force_authenticate(user)

    def create_link(self):
        return self.client.post(
            '/api/invitation_links/',
            {'target_type': 'team', 'target_id': self.team.id},
            format='json',
        )

    def test_closed_team_blocks_link_lifecycle_without_revoking_active_token(self):
        self.authenticate(self.team_admin)
        created = self.create_link()
        self.team.visibility = 'closed'
        self.team.save(update_fields=['visibility'])

        blocked_create = self.create_link()
        blocked_regenerate = self.client.post(
            f"/api/invitation_links/{created.data['id']}/regenerate/",
            {},
            format='json',
        )
        blocked_accept = self.client.post(
            '/api/invitation_links/accept/',
            {'token': created.data['token']},
            format='json',
        )
        self.client.force_authenticate(user=None)
        blocked_resolve = self.client.get(
            '/api/invitation_links/resolve/',
            {'token': created.data['token']},
        )

        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(blocked_create.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(blocked_regenerate.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(blocked_accept.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(blocked_resolve.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(InvitationLink.objects.get(pk=created.data['id']).is_active)

        self.team.visibility = 'private'
        self.team.save(update_fields=['visibility'])
        reopened = self.client.get(
            '/api/invitation_links/resolve/',
            {'token': created.data['token']},
        )
        self.assertEqual(reopened.status_code, status.HTTP_200_OK)

    def test_closed_team_link_can_still_be_revoked(self):
        self.authenticate(self.team_admin)
        created = self.create_link()
        self.team.visibility = 'closed'
        self.team.save(update_fields=['visibility'])

        revoked = self.client.post(
            f"/api/invitation_links/{created.data['id']}/revoke/"
        )

        self.assertEqual(revoked.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(InvitationLink.objects.get(pk=created.data['id']).is_active)
