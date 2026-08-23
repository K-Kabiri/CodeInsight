from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient, APITestCase


class TokenObtainTest(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="alice",
            password="s3cret-pass",
        )

    def test_valid_credentials_issue_a_token(self):
        response = self.client.post(
            "/api/auth/token/",
            {"username": "alice", "password": "s3cret-pass"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        token = Token.objects.get(user=self.user)
        self.assertEqual(response.data, {"token": token.key})

    def test_wrong_password_is_rejected_without_issuing_a_token(self):
        response = self.client.post(
            "/api/auth/token/",
            {"username": "alice", "password": "wrong-password"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("non_field_errors", response.data)
        self.assertFalse(
            Token.objects.filter(user=self.user).exists()
        )

    def test_unknown_username_is_rejected(self):
        response = self.client.post(
            "/api/auth/token/",
            {"username": "nobody", "password": "whatever"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_missing_credentials_are_rejected(self):
        response = self.client.post(
            "/api/auth/token/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_existing_token_is_reused(self):
        existing = Token.objects.create(user=self.user)
        response = self.client.post(
            "/api/auth/token/",
            {"username": "alice", "password": "s3cret-pass"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"token": existing.key})
        self.assertEqual(
            Token.objects.filter(user=self.user).count(),
            1,
        )

    def test_obtained_token_authenticates_a_request(self):
        response = self.client.post(
            "/api/auth/token/",
            {"username": "alice", "password": "s3cret-pass"},
            format="json",
        )
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f"Token {response.data['token']}"
        )
        me = client.get("/api/me/")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.data["username"], "alice")


class MeEndpointTest(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="alice",
            password="s3cret-pass",
        )

    def test_unauthenticated_request_returns_401(self):
        response = self.client.get("/api/me/")
        self.assertEqual(response.status_code, 401)

    def test_authenticated_request_is_recognized(self):
        token = Token.objects.create(user=self.user)
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f"Token {token.key}"
        )
        response = client.get("/api/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            {"id": self.user.id, "username": "alice"},
        )

    def test_invalid_token_is_rejected(self):
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION="Token not-a-real-token"
        )
        response = client.get("/api/me/")
        self.assertEqual(response.status_code, 401)
