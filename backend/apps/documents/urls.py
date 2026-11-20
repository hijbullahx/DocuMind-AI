"""
URL Routing configuration for Document Intelligence REST API.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.documents.auth_views import (
    CurrentUserView,
    HealthCheckView,
    LoginView,
    LogoutView,
    RefreshTokenView,
)
from apps.documents.views import (
    CrossReconciliationViewSet,
    DocumentViewSet,
)

router = DefaultRouter()
router.register(r'documents', DocumentViewSet, basename='document')
router.register(r'reconciliations', CrossReconciliationViewSet, basename='reconciliation')

urlpatterns = [
    # Public & Authenticated Auth & Health Endpoints
    path('auth/login/', LoginView.as_view(), name='auth-login'),
    path('auth/refresh/', RefreshTokenView.as_view(), name='auth-refresh'),
    path('auth/me/', CurrentUserView.as_view(), name='auth-me'),
    path('auth/logout/', LogoutView.as_view(), name='auth-logout'),
    path('health/', HealthCheckView.as_view(), name='health-check'),

    # ViewSet Resources
    path('', include(router.urls)),
]
