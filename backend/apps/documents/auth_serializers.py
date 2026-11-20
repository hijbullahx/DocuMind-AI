"""
Authentication Serializers for DocuMind-AI REST API.
Provides validation and serialization for login, user profiles, and JWT tokens.
"""
from typing import Any, Dict
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken


class UserSerializer(serializers.ModelSerializer):
    """Serializes authenticated user profile information."""
    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "is_staff",
            "is_superuser",
            "date_joined",
            "last_login",
        ]
        read_only_fields = fields


class LoginSerializer(serializers.Serializer):
    """
    Validates user credentials and issues JWT access and refresh tokens.
    Enforces safe, non-revealing error messages on failed attempts.
    """
    username = serializers.CharField(required=True, trim_whitespace=True)
    password = serializers.CharField(required=True, write_only=True, style={"input_type": "password"})

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        username = attrs.get("username", "").strip()
        password = attrs.get("password", "")

        if not username or not password:
            raise serializers.ValidationError({"detail": "Must provide both username and password."})

        request = self.context.get("request")
        user = authenticate(request=request, username=username, password=password)

        if not user:
            # Check if user exists with valid password but is inactive
            existing = User.objects.filter(username=username).first()
            if existing and existing.check_password(password) and not existing.is_active:
                raise serializers.ValidationError({"detail": "User account is disabled."})
            # Generic message prevents user enumeration attacks
            raise serializers.ValidationError({"detail": "Invalid username or password."})

        if not user.is_active:
            raise serializers.ValidationError({"detail": "User account is disabled."})

        # Generate JWT Token Pair
        refresh = RefreshToken.for_user(user)
        access = str(refresh.access_token)

        attrs["user"] = user
        attrs["access"] = access
        attrs["refresh"] = str(refresh)
        return attrs


class TokenRefreshResponseSerializer(serializers.Serializer):
    """Serializes refreshed access token response."""
    access = serializers.CharField()
