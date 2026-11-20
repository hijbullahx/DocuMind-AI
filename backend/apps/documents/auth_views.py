"""
Authentication & System Health Views for DocuMind-AI REST API.
Provides endpoints for user login, token refresh, profile inspection, logout, and health monitoring.
"""
import logging
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.views import TokenRefreshView

from apps.documents.auth_serializers import LoginSerializer, UserSerializer

logger = logging.getLogger(__name__)


class LoginView(APIView):
    """
    Authenticates user with username and password.
    Returns JWT access token, refresh token, and user profile.
    """
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        username = request.data.get("username", "")
        password = request.data.get("password", "")
        if not username or not password:
            return Response(
                {"detail": "Must provide both username and password.", "error": "Validation error."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = LoginSerializer(data=request.data, context={"request": request})
        if not serializer.is_valid():
            detail = serializer.errors.get("detail", ["Invalid username or password."])
            if isinstance(detail, list):
                detail = detail[0]
            return Response(
                {"detail": str(detail), "error": "Authentication failed."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        data = serializer.validated_data
        user = data["user"]
        user_data = UserSerializer(user).data

        logger.info(f"[Auth] Successful login for user: {user.username}")

        return Response(
            {
                "access": data["access"],
                "refresh": data["refresh"],
                "user": user_data,
                "message": "Authentication successful.",
            },
            status=status.HTTP_200_OK,
        )


class RefreshTokenView(TokenRefreshView):
    """
    Issues a renewed access token from a valid refresh token.
    Publicly accessible to allow token rotation.
    """
    permission_classes = [AllowAny]


class CurrentUserView(APIView):
    """
    Returns the authenticated user's profile details.
    Requires valid JWT or session authentication.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        serializer = UserSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class LogoutView(APIView):
    """
    Handles user logout.
    Acknowledges client logout and optionally blacklists the refresh token if provided.
    """
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        refresh_token = request.data.get("refresh")
        if refresh_token:
            try:
                from rest_framework_simplejwt.tokens import RefreshToken
                token = RefreshToken(refresh_token)
                token.blacklist()
            except Exception:
                # If blacklisting is not configured or token is already invalid, proceed cleanly
                pass

        username = request.user.username if request.user and request.user.is_authenticated else "anonymous"
        logger.info(f"[Auth] Logout completed for user: {username}")
        return Response(
            {"message": "Logged out successfully."},
            status=status.HTTP_200_OK,
        )


class HealthCheckView(APIView):
    """
    Public health check endpoint for frontend connectivity and load balancer probing.
    Does not require authentication.
    """
    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        return Response(
            {
                "status": "ok",
                "app": "DocuMind-AI",
                "version": "1.0",
                "timestamp": timezone.now().isoformat(),
            },
            status=status.HTTP_200_OK,
        )
