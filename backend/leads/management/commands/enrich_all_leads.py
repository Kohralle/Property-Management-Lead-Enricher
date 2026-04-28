from __future__ import annotations

import asyncio

from django.core.management.base import BaseCommand

from leads.enrichment.pipeline import enrich_person
from leads.models import Person


class Command(BaseCommand):
    help = "Run the enrichment pipeline for every lead without an EnrichmentResult."

    def handle(self, *args, **options):
        asyncio.run(self._run())

    async def _run(self):
        leads = [
            lead async for lead in Person.objects.select_related("building").filter(enrichments__isnull=True)
        ]
        if not leads:
            self.stdout.write("No unenriched leads found.")
            return

        self.stdout.write(f"Enriching {len(leads)} lead(s)...")
        created = 0

        for lead in leads:
            result = await enrich_person(lead)
            created += 1
            self.stdout.write(
                f"[{created}/{len(leads)}] {lead.name} <{lead.email}> -> "
                f"{result.score_tier} ({result.score_total})"
            )

        self.stdout.write(self.style.SUCCESS(f"Created {created} enrichment result(s)."))
