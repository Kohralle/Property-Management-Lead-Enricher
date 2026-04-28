from django.contrib import admin
from .models import Building, Person, EnrichmentResult

admin.site.register(Building)
admin.site.register(Person)


@admin.register(EnrichmentResult)
class EnrichmentResultAdmin(admin.ModelAdmin):
    list_display = ("lead", "score_tier", "score_total", "created_at")
    list_filter = ("score_tier",)
    search_fields = ("lead__company", "lead__name")
    readonly_fields = ("created_at", "updated_at", "raw_enrichment", "score_breakdown")
