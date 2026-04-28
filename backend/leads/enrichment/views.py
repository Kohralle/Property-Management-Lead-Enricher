from asgiref.sync import async_to_sync
from django.http import Http404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from leads.enrichment.pipeline import enrich_person
from leads.models import Person
from leads.serializers import EnrichmentResultSerializer

class EnrichLeadView(APIView):
    def post(self, request, lead_id: int) -> Response:
        try:
            lead = Person.objects.select_related("building").get(id=lead_id)
        except Person.DoesNotExist as exc:
            raise Http404("Lead not found") from exc

        result = async_to_sync(enrich_person)(lead)
        serializer = EnrichmentResultSerializer(result)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
