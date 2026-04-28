from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import BuildingViewSet, EnrichmentResultViewSet, PersonViewSet

router = DefaultRouter()
router.register('buildings', BuildingViewSet)
router.register('persons', PersonViewSet)
router.register('enrichments', EnrichmentResultViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('', include('leads.enrichment.urls')),
]
