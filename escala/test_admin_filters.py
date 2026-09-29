from datetime import date, time

from django.contrib import admin
from django.test import TestCase
from django.urls import reverse

from escala.models import (
    Organization,
    OrganizationInvitation,
    Schedule,
    ScheduleParticipation,
    Team,
    TeamInvitation,
    Unavailability,
    User,
)


class OperationalAdminFiltersTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            email='admin@example.com',
            password='test-password',
            first_name='Admin',
        )
        self.alpha_user = User.objects.create_user(
            email='alpha@example.com',
            password='test-password',
            first_name='Alpha',
            last_name='Member',
        )
        self.beta_user = User.objects.create_user(
            email='beta@example.com',
            password='test-password',
            first_name='Beta',
            last_name='Member',
        )
        self.alpha_organization = Organization.objects.create(name='Alpha Organization')
        self.beta_organization = Organization.objects.create(name='Beta Organization')
        self.alpha_team = Team.objects.create(
            name='Alpha Team',
            organization=self.alpha_organization,
            visibility=Team.Visibility.DISCOVERABLE,
        )
        self.beta_team = Team.objects.create(
            name='Beta Team',
            organization=self.beta_organization,
            visibility=Team.Visibility.PRIVATE,
        )
        self.alpha_schedule = Schedule.objects.create(
            name='Alpha Event',
            team=self.alpha_team,
            date=date(2026, 10, 10),
            hour=time(9, 0),
        )
        self.beta_schedule = Schedule.objects.create(
            name='Beta Event',
            team=self.beta_team,
            date=date(2026, 11, 10),
            hour=time(19, 0),
        )
        self.alpha_participation = ScheduleParticipation.objects.create(
            schedule=self.alpha_schedule,
            user=self.alpha_user,
            confirmation=True,
        )
        self.beta_participation = ScheduleParticipation.objects.create(
            schedule=self.beta_schedule,
            user=self.beta_user,
            confirmation=False,
        )
        self.alpha_unavailability = Unavailability.objects.create(
            description='Alpha vacation',
            user=self.alpha_user,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 5),
        )
        self.beta_unavailability = Unavailability.objects.create(
            description='Beta vacation',
            user=self.beta_user,
            start_date=date(2026, 11, 1),
            end_date=date(2026, 11, 5),
        )
        self.alpha_team_invitation = TeamInvitation.objects.create(
            recipient_email='alpha-invite@example.com',
            sender_name='Alpha Sender',
            team=self.alpha_team,
        )
        self.beta_team_invitation = TeamInvitation.objects.create(
            recipient_email='beta-invite@example.com',
            sender_name='Beta Sender',
            team=self.beta_team,
        )
        self.alpha_organization_invitation = OrganizationInvitation.objects.create(
            recipient_email='alpha-org-invite@example.com',
            sender_name='Alpha Sender',
            organization=self.alpha_organization,
        )
        self.beta_organization_invitation = OrganizationInvitation.objects.create(
            recipient_email='beta-org-invite@example.com',
            sender_name='Beta Sender',
            organization=self.beta_organization,
        )
        self.client.force_login(self.superuser)

    def assert_changelist_results(self, model, params, expected):
        response = self.client.get(
            reverse(f'admin:escala_{model._meta.model_name}_changelist'),
            params,
        )

        self.assertEqual(response.status_code, 200)
        self.assertSetEqual(set(response.context['cl'].result_list), set(expected))

    def test_operational_admins_declare_expected_filters_and_searches(self):
        expectations = {
            Team: {
                'list_filter': ('organization', 'visibility'),
                'search_fields': ('name', 'code_access'),
                'list_select_related': ('organization',),
            },
            Schedule: {
                'list_filter': ('team', 'date'),
                'search_fields': ('name', 'team__name'),
                'list_select_related': ('team',),
            },
            ScheduleParticipation: {
                'list_filter': ('confirmation', 'schedule__team'),
                'search_fields': (
                    'schedule__name',
                    'user__email',
                    'user__first_name',
                    'user__last_name',
                ),
                'list_select_related': ('schedule', 'schedule__team', 'user'),
            },
            Unavailability: {
                'list_filter': ('start_date', 'end_date'),
                'search_fields': (
                    'description',
                    'user__email',
                    'user__first_name',
                    'user__last_name',
                ),
                'list_select_related': ('user',),
            },
            TeamInvitation: {
                'list_filter': ('team',),
                'search_fields': ('recipient_email', 'sender_name', 'team__name'),
                'list_select_related': ('team',),
            },
            OrganizationInvitation: {
                'list_filter': ('organization',),
                'search_fields': (
                    'recipient_email',
                    'sender_name',
                    'organization__name',
                ),
                'list_select_related': ('organization',),
            },
        }

        for model, expected in expectations.items():
            with self.subTest(model=model.__name__):
                model_admin = admin.site._registry[model]
                self.assertEqual(model_admin.list_filter, expected['list_filter'])
                self.assertEqual(model_admin.search_fields, expected['search_fields'])
                self.assertEqual(
                    model_admin.list_select_related,
                    expected['list_select_related'],
                )

    def test_team_filter_and_search_are_combined(self):
        self.assert_changelist_results(
            Team,
            {
                'q': 'Alpha Team',
                'organization__id__exact': self.alpha_organization.id,
                'visibility__exact': Team.Visibility.DISCOVERABLE,
            },
            [self.alpha_team],
        )

    def test_schedule_filter_and_search_are_combined(self):
        self.assert_changelist_results(
            Schedule,
            {'q': 'Alpha Event', 'team__id__exact': self.alpha_team.id},
            [self.alpha_schedule],
        )

    def test_participation_filter_and_search_are_combined(self):
        self.assert_changelist_results(
            ScheduleParticipation,
            {
                'q': self.alpha_user.email,
                'confirmation__exact': '1',
                'schedule__team__id__exact': self.alpha_team.id,
            },
            [self.alpha_participation],
        )

    def test_unavailability_filter_and_search_are_combined(self):
        self.assert_changelist_results(
            Unavailability,
            {'q': 'Alpha vacation', 'start_date__gte': '2026-10-01'},
            [self.alpha_unavailability],
        )

    def test_team_invitation_filter_and_search_are_combined(self):
        self.assert_changelist_results(
            TeamInvitation,
            {
                'q': 'alpha-invite@example.com',
                'team__id__exact': self.alpha_team.id,
            },
            [self.alpha_team_invitation],
        )

    def test_organization_invitation_filter_and_search_are_combined(self):
        self.assert_changelist_results(
            OrganizationInvitation,
            {
                'q': 'alpha-org-invite@example.com',
                'organization__id__exact': self.alpha_organization.id,
            },
            [self.alpha_organization_invitation],
        )
