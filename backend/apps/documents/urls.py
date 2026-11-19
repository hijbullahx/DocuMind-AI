"""
URL Routing configuration for Document Intelligence REST API.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.documents.views import (
    CrossReconciliationViewSet,
    DocumentViewSet,
)

router = DefaultRouter()
router.register(r'documents', DocumentViewSet, basename='document')
router.register(r'reconciliations', CrossReconciliationViewSet, basename='reconciliation')

urlpatterns = [
    path('', include(router.urls)),
]
