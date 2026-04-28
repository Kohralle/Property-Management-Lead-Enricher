from typing import Optional

from rest_framework import serializers
from .models import Building, EnrichmentResult, Person


class BuildingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Building
        fields = '__all__'


class PersonSerializer(serializers.ModelSerializer):
    building_detail = BuildingSerializer(source='building', read_only=True)
    has_enrichment = serializers.SerializerMethodField()
    latest_enrichment_id = serializers.SerializerMethodField()
    latest_enrichment_tier = serializers.SerializerMethodField()

    class Meta:
        model = Person
        fields = [
            'id',
            'name',
            'email',
            'company',
            'building',
            'building_detail',
            'has_enrichment',
            'latest_enrichment_id',
            'latest_enrichment_tier',
            'created_at',
            'updated_at',
        ]

    def get_has_enrichment(self, obj: Person) -> bool:
        annotated = getattr(obj, 'has_enrichment', None)
        if annotated is not None:
            return bool(annotated)
        return obj.enrichments.exists()

    def get_latest_enrichment_id(self, obj: Person) -> Optional[int]:
        annotated = getattr(obj, 'latest_enrichment_id', None)
        if annotated is not None:
            return annotated
        latest = obj.enrichments.first()
        return latest.id if latest else None

    def get_latest_enrichment_tier(self, obj: Person) -> Optional[str]:
        annotated = getattr(obj, 'latest_enrichment_tier', None)
        if annotated is not None:
            return annotated
        latest = obj.enrichments.first()
        return latest.score_tier if latest else None


class EnrichmentResultSerializer(serializers.ModelSerializer):
    lead_detail = PersonSerializer(source='lead', read_only=True)

    class Meta:
        model = EnrichmentResult
        fields = [
            'id',
            'lead',
            'lead_detail',
            'score_total',
            'score_tier',
            'score_breakdown',
            'email_subject',
            'email_body',
            'insights',
            'raw_enrichment',
            'created_at',
            'updated_at',
        ]
