from django.contrib import admin
from django.contrib.auth.models import Group, Permission
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from rest_framework import status
from rest_framework.test import APIClient

from escala.models import Organization, OrganizationCreationRequest, User


CREATOR_GROUP_NAME = 'Organization Creators'


class OrganizationCreatorGroupMigrationTests(TransactionTestCase):
    migrate_from = [('escala', '0011_team_visibility')]
    migrate_to = [('escala', '0012_sync_organization_creator_group')]

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state(self.migrate_from).apps
        group_model = old_apps.get_model('auth', 'Group')
        permission_model = old_apps.get_model('auth', 'Permission')
        permission = permission_model.objects.get(
            content_type__app_label='escala',
            codename='add_organization',
        )
        users_group, _ = group_model.objects.get_or_create(name='Users')
        users_group.permissions.add(permission)
        creator_group, _ = group_model.objects.get_or_create(
            name=CREATOR_GROUP_NAME
        )
        creator_group.permissions.clear()

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        self.apps = executor.loader.project_state(self.migrate_to).apps

    def tearDown(self):
        MigrationExecutor(connection).migrate(
            MigrationExecutor(connection).loader.graph.leaf_nodes()
        )
        super().tearDown()

    def test_migration_moves_add_organization_to_creator_group(self):
        group_model = self.apps.get_model('auth', 'Group')
        users_group = group_model.objects.get(name='Users')
        creator_group = group_model.objects.get(name=CREATOR_GROUP_NAME)

        self.assertFalse(
            users_group.permissions.filter(codename='add_organization').exists()
        )
        self.assertEqual(
            list(creator_group.permissions.values_list('codename', flat=True)),
            ['add_organization'],
        )


class OrganizationCreationPermissionApiTests(TestCase):
    def setUp(self):
        self.ordinary = User.objects.create_user(
            email='ordinary@example.com',
            password='test-password',
            first_name='Ordinary',
        )
        self.creator = User.objects.create_user(
            email='creator@example.com',
            password='test-password',
            first_name='Creator',
        )
        self.outsider = User.objects.create_user(
            email='outsider@example.com',
            password='test-password',
            first_name='Outsider',
        )
        self.superuser = User.objects.create_superuser(
            email='superuser@example.com',
            password='test-password',
            first_name='Superuser',
        )
        self.creator_group = Group.objects.get(name=CREATOR_GROUP_NAME)
        self.creator.groups.add(self.creator_group)
        self.client = APIClient()

    def test_creator_directly_creates_organization_with_server_owned_memberships(self):
        self.client.force_authenticate(self.creator)

        response = self.client.post(
            '/api/organizations/',
            {
                'name': 'Community Church',
                'admins': [self.outsider.id],
                'members': [self.outsider.id],
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        organization = Organization.objects.get(name='Community Church')
        self.assertTrue(organization.admins.filter(pk=self.creator.pk).exists())
        self.assertTrue(organization.members.filter(pk=self.creator.pk).exists())
        self.assertFalse(organization.admins.filter(pk=self.outsider.pk).exists())
        self.assertFalse(organization.members.filter(pk=self.outsider.pk).exists())
        self.assertEqual(response.data['admins'][0]['id'], self.creator.id)
        self.assertEqual(response.data['members'][0]['id'], self.creator.id)

    def test_ordinary_user_and_direct_permission_without_group_receive_403(self):
        permission = Permission.objects.get(
            content_type__app_label='escala',
            codename='add_organization',
        )
        self.outsider.user_permissions.add(permission)

        for user in [self.ordinary, self.outsider]:
            with self.subTest(user=user.email):
                self.client.force_authenticate(user)
                response = self.client.post(
                    '/api/organizations/',
                    {'name': f'Forbidden {user.id}'},
                    format='json',
                )

                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.assertEqual(Organization.objects.count(), 0)

    def test_creator_group_membership_without_permission_receives_403(self):
        self.creator_group.permissions.clear()
        self.client.force_authenticate(self.creator)

        response = self.client.post(
            '/api/organizations/',
            {'name': 'Missing Permission'},
            format='json',
        )
        capability_response = self.client.get(f'/api/users/{self.creator.id}/')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(capability_response.data['can_create_organization'])
        self.assertFalse(Organization.objects.exists())

    def test_superuser_can_create_without_creator_group_membership(self):
        self.client.force_authenticate(self.superuser)

        response = self.client.post(
            '/api/organizations/',
            {'name': 'Platform Organization'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        organization = Organization.objects.get(name='Platform Organization')
        self.assertTrue(organization.admins.filter(pk=self.superuser.pk).exists())
        self.assertTrue(organization.members.filter(pk=self.superuser.pk).exists())

    def test_retrieve_and_login_expose_creation_capability(self):
        self.client.force_authenticate(self.creator)
        creator_response = self.client.get(f'/api/users/{self.creator.id}/')
        ordinary_response = self.client.get(f'/api/users/{self.ordinary.id}/')
        self.client.force_authenticate(user=None)
        login_response = self.client.post(
            '/api/token/',
            {'email': self.creator.email, 'password': 'test-password'},
            format='json',
        )

        self.assertTrue(creator_response.data['can_create_organization'])
        self.assertFalse(ordinary_response.data['can_create_organization'])
        self.assertTrue(login_response.data['user']['can_create_organization'])

    def test_legacy_request_route_is_removed_and_model_is_not_registered(self):
        self.client.force_authenticate(self.ordinary)

        list_response = self.client.get('/api/organization_requests/')
        create_response = self.client.post(
            '/api/organization_requests/',
            {'name': 'Legacy Request'},
            format='json',
        )

        self.assertEqual(list_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(create_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(admin.site.is_registered(OrganizationCreationRequest))

        legacy_record = OrganizationCreationRequest.objects.create(
            requester=self.ordinary,
            name='Preserved Legacy Record',
        )
        self.assertTrue(
            OrganizationCreationRequest.objects.filter(pk=legacy_record.pk).exists()
        )
