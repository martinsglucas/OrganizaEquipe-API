from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from escala.models import Organization, Schedule, Team, User


class ScheduleNotesApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="schedule-notes-admin@example.com",
            password="test-password",
            first_name="Admin",
        )
        self.member = User.objects.create_user(
            email="schedule-notes-member@example.com",
            password="test-password",
            first_name="Member",
        )
        organization = Organization.objects.create(name="Notes Organization")
        organization.members.add(self.admin, self.member)
        self.team = Team.objects.create(name="Notes Team", organization=organization)
        self.team.admins.add(self.admin)
        self.team.members.add(self.admin, self.member)
        self.client = APIClient()

    def schedule_payload(self, **overrides):
        payload = {
            "name": "Sunday Schedule",
            "team": self.team.id,
            "date": "2026-08-09",
            "hour": "19:00:00",
            "participations": [],
        }
        payload.update(overrides)
        return payload

    def test_admin_can_create_schedule_with_notes(self):
        self.client.force_authenticate(self.admin)

        response = self.client.post(
            "/api/schedules/",
            self.schedule_payload(notes="Chegar 30 minutos antes."),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["notes"], "Chegar 30 minutos antes.")
        self.assertEqual(
            Schedule.objects.get().notes,
            "Chegar 30 minutos antes.",
        )

    def test_admin_can_update_schedule_notes(self):
        schedule = Schedule.objects.create(
            name="Sunday Schedule",
            team=self.team,
            date="2026-08-09",
            hour="19:00:00",
        )
        self.client.force_authenticate(self.admin)

        response = self.client.put(
            f"/api/schedules/{schedule.id}/",
            self.schedule_payload(notes="Nova orientação para a equipe."),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        schedule.refresh_from_db()
        self.assertEqual(schedule.notes, "Nova orientação para a equipe.")
        self.assertEqual(response.data["notes"], "Nova orientação para a equipe.")

    def test_member_can_retrieve_schedule_notes(self):
        schedule = Schedule.objects.create(
            name="Sunday Schedule",
            team=self.team,
            date="2026-08-09",
            hour="19:00:00",
            notes="Levar o material da apresentação.",
        )
        self.client.force_authenticate(self.member)

        response = self.client.get(f"/api/schedules/{schedule.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["notes"], "Levar o material da apresentação.")

    def test_empty_or_omitted_notes_are_stored_as_empty_text(self):
        self.client.force_authenticate(self.admin)

        omitted_response = self.client.post(
            "/api/schedules/",
            self.schedule_payload(name="Without notes"),
            format="json",
        )
        empty_response = self.client.post(
            "/api/schedules/",
            self.schedule_payload(name="Empty notes", notes=""),
            format="json",
        )

        self.assertEqual(omitted_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(empty_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(omitted_response.data["notes"], "")
        self.assertEqual(empty_response.data["notes"], "")
        self.assertEqual(Schedule.objects.get(name="Without notes").notes, "")
        self.assertEqual(Schedule.objects.get(name="Empty notes").notes, "")
