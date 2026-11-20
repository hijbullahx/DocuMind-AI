"""
Automated Test Suite for TASK-020: Authentication & User Profile API.
Tests:
- Login with valid credentials returns JWT tokens and user profile
- Login with invalid password returns generic 401 error
- Login with nonexistent user returns generic 401 error
- Login with disabled user returns 401 error
- Login with missing username or password returns 400 error
- Token refresh with valid refresh token returns new access token
- Token refresh with invalid/expired token returns 401 error
- Current user profile endpoint returns 200 with user data when authenticated
- Current user profile endpoint returns 401 when unauthenticated
- Logout endpoint returns 200 OK
- Health check endpoint is publicly accessible without authentication
"""
import os
import sys
import unittest.mock as mock

for mod in ["celery", "celery.shared_task", "pymupdf", "fitz", "pdfplumber", "easyocr"]:
    if mod not in sys.modules:
        sys.modules[mod] = mock.MagicMock()

import django
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "documind.settings")
django.setup()

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken


@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    """Applies database migrations for test session."""
    call_command("migrate", verbosity=0)


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def standard_user():
    """Creates a standard test user with known password."""
    user, created = User.objects.get_or_create(
        username="compliance_auditor",
        defaults={"email": "auditor@documind.ai", "first_name": "Compliance", "last_name": "Auditor"},
    )
    user.set_password("SecurePassword2026!")
    user.is_active = True
    user.save()
    return user


@pytest.fixture
def disabled_user():
    """Creates a disabled user account."""
    user, _ = User.objects.get_or_create(
        username="deactivated_user",
        defaults={"email": "deactivated@documind.ai"},
    )
    user.set_password("SomePassword123!")
    user.is_active = False
    user.save()
    return user


@pytest.mark.django_db
class TestAuthenticationAPI:
    """Verifies authentication lifecycle endpoints."""

    def test_login_success(self, api_client, standard_user):
        """Valid credentials return 200 OK, JWT tokens, and user profile."""
        res = api_client.post(
            "/api/auth/login/",
            data={"username": "compliance_auditor", "password": "SecurePassword2026!"},
            format="json",
        )
        assert res.status_code == status.HTTP_200_OK
        data = res.json()
        assert "access" in data
        assert "refresh" in data
        assert "user" in data
        assert data["user"]["username"] == "compliance_auditor"
        assert data["user"]["email"] == "auditor@documind.ai"

    def test_login_invalid_password_returns_generic_error(self, api_client, standard_user):
        """Invalid password returns 401 with generic non-revealing error message."""
        res = api_client.post(
            "/api/auth/login/",
            data={"username": "compliance_auditor", "password": "WrongPassword!"},
            format="json",
        )
        assert res.status_code == status.HTTP_401_UNAUTHORIZED
        data = res.json()
        assert "access" not in data
        assert data.get("detail") == "Invalid username or password."

    def test_login_nonexistent_user_returns_generic_error(self, api_client):
        """Nonexistent username returns same generic 401 error (prevents user enumeration)."""
        res = api_client.post(
            "/api/auth/login/",
            data={"username": "unknown_ghost_user", "password": "AnyPassword!"},
            format="json",
        )
        assert res.status_code == status.HTTP_401_UNAUTHORIZED
        data = res.json()
        assert "access" not in data
        assert data.get("detail") == "Invalid username or password."

    def test_login_disabled_user_rejected(self, api_client, disabled_user):
        """Disabled user account cannot authenticate."""
        res = api_client.post(
            "/api/auth/login/",
            data={"username": "deactivated_user", "password": "SomePassword123!"},
            format="json",
        )
        assert res.status_code == status.HTTP_401_UNAUTHORIZED
        assert "disabled" in res.json().get("detail", "").lower()

    def test_login_missing_fields_returns_400(self, api_client):
        """Omitting username or password returns 400 Bad Request."""
        res = api_client.post(
            "/api/auth/login/",
            data={"username": "compliance_auditor"},
            format="json",
        )
        assert res.status_code == status.HTTP_400_BAD_REQUEST

    def test_token_refresh_success(self, api_client, standard_user):
        """Submitting a valid refresh token yields a new access token."""
        refresh = RefreshToken.for_user(standard_user)
        res = api_client.post(
            "/api/auth/refresh/",
            data={"refresh": str(refresh)},
            format="json",
        )
        assert res.status_code == status.HTTP_200_OK
        data = res.json()
        assert "access" in data
        assert len(data["access"]) > 20

    def test_token_refresh_invalid_rejected(self, api_client):
        """Submitting an invalid refresh token returns 401 Unauthorized."""
        res = api_client.post(
            "/api/auth/refresh/",
            data={"refresh": "invalid-token-string-xyz"},
            format="json",
        )
        assert res.status_code == status.HTTP_401_UNAUTHORIZED

    def test_current_user_profile_authenticated(self, api_client, standard_user):
        """Authenticated request to /api/auth/me/ returns user details."""
        api_client.force_authenticate(user=standard_user)
        res = api_client.get("/api/auth/me/")
        assert res.status_code == status.HTTP_200_OK
        data = res.json()
        assert data["username"] == "compliance_auditor"
        assert data["email"] == "auditor@documind.ai"

    def test_current_user_profile_unauthenticated_rejected(self, api_client):
        """Unauthenticated request to /api/auth/me/ returns 401 Unauthorized."""
        res = api_client.get("/api/auth/me/")
        assert res.status_code == status.HTTP_401_UNAUTHORIZED

    def test_logout_endpoint(self, api_client, standard_user):
        """Logout endpoint returns 200 OK and clean message."""
        api_client.force_authenticate(user=standard_user)
        res = api_client.post("/api/auth/logout/", data={}, format="json")
        assert res.status_code == status.HTTP_200_OK
        assert "message" in res.json()

    def test_health_endpoint_public(self, api_client):
        """Health check endpoint is publicly accessible without any credentials."""
        res = api_client.get("/api/health/")
        assert res.status_code == status.HTTP_200_OK
        data = res.json()
        assert data["status"] == "ok"
        assert data["app"] == "DocuMind-AI"
