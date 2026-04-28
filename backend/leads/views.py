from django.db.models import Exists, OuterRef, Subquery
from rest_framework import filters, mixins, viewsets

from .models import Building, EnrichmentResult, Person
from .serializers import BuildingSerializer, EnrichmentResultSerializer, PersonSerializer


class BuildingViewSet(viewsets.ModelViewSet):
    queryset = Building.objects.all().order_by('-created_at')
    serializer_class = BuildingSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['property_address', 'city', 'state', 'country']


class PersonViewSet(viewsets.ModelViewSet):
    latest_enrichment = EnrichmentResult.objects.filter(lead=OuterRef('pk')).order_by('-created_at')
    queryset = Person.objects.select_related('building').annotate(
        has_enrichment=Exists(latest_enrichment),
        latest_enrichment_id=Subquery(latest_enrichment.values('id')[:1]),
        latest_enrichment_tier=Subquery(latest_enrichment.values('score_tier')[:1]),
    ).order_by('-created_at')
    serializer_class = PersonSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'email', 'company', 'building__property_address', 'building__city']


class EnrichmentResultViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = EnrichmentResult.objects.select_related('lead', 'lead__building').all()
    serializer_class = EnrichmentResultSerializer
