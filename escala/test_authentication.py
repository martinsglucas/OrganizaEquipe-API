from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from escala.models import User


class RefreshTokenCookieTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.credentials = {
            "email": "session@example.com",
            "password": "test-password",
        }
        User.objects.create_user(
            email=self.credentials["email"],
            password=self.credentials["password"],
            first_name="Session User",
        )

    @override_settings(DEBUG=True)
    def test_local_login_uses_browser_compatible_refresh_cookie(self):
        response = self.client.post("/api/token/", self.credentials)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        cookie = response.cookies["refreshToken"]
        self.assertFalse(cookie["secure"])
        self.assertEqual(cookie["samesite"], "Lax")
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["path"], "/api/token/")

    @override_settings(DEBUG=False)
    def test_production_login_uses_cross_origin_secure_refresh_cookie(self):
        response = self.client.post("/api/token/", self.credentials)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        cookie = response.cookies["refreshToken"]
        self.assertTrue(cookie["secure"])
        self.assertEqual(cookie["samesite"], "None")

    @override_settings(DEBUG=True)
    def test_local_refresh_rotates_browser_compatible_cookie(self):
        login_response = self.client.post("/api/token/", self.credentials)
        self.client.cookies["refreshToken"] = login_response.cookies["refreshToken"].value

        response = self.client.post("/api/token/refresh/", {})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        cookie = response.cookies["refreshToken"]
        self.assertFalse(cookie["secure"])
        self.assertEqual(cookie["samesite"], "Lax")
