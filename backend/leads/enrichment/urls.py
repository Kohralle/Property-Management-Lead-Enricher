from django.urls import path

from .views import EnrichLeadView

urlpatterns = [
    path('enrich/<int:lead_id>/', EnrichLeadView.as_view(), name='enrich-lead'),
]
