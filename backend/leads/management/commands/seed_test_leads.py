from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from leads.models import Building, Person

SEED_LEADS = [
    {
        "name": "Sarah Chen",
        "email": "sarah.chen@bozzuto.com",
        "company": "The Bozzuto Group",
        "property_address": "1700 Clarendon Blvd",
        "city": "Arlington",
        "state": "VA",
        "country": "US",
    },
    {
        "name": "Mike Rodriguez",
        "email": "m.rodriguez@greystar.com",
        "company": "Greystar Real Estate Partners",
        "property_address": "750 S Gay St",
        "city": "Knoxville",
        "state": "TN",
        "country": "US",
    },
    {
        "name": "Jennifer Park",
        "email": "jpark@avaloncommunities.com",
        "company": "AvalonBay Communities",
        "property_address": "671 N Glebe Rd",
        "city": "Arlington",
        "state": "VA",
        "country": "US",
    },
    {
        "name": "David Kim",
        "email": "david@kittlepg.com",
        "company": "Kittle Property Group",
        "property_address": "500 E 96th St",
        "city": "Indianapolis",
        "state": "IN",
        "country": "US",
    },
    {
        "name": "Lisa Thompson",
        "email": "lisa.t@balfourbeatty.com",
        "company": "Balfour Beatty Communities",
        "property_address": "10350 Ormsby Park Pl",
        "city": "Louisville",
        "state": "KY",
        "country": "US",
    },
    {
        "name": "Kris Sunga",
        "email": "Kris@tripalink.com",
        "company": "Tripalink",
        "property_address": "4231 12th Ave NE",
        "city": "Seattle",
        "state": "WA",
        "country": "US",
    },
]


class Command(BaseCommand):
    help = "Create or update sample leads for enrichment testing."

    @transaction.atomic
    def handle(self, *args, **options):
        created_people = 0
        updated_people = 0
        created_buildings = 0

        for item in SEED_LEADS:
            building, building_created = Building.objects.get_or_create(
                property_address=item["property_address"],
                city=item["city"],
                state=item["state"],
                defaults={"country": item["country"]},
            )
            if building_created:
                created_buildings += 1
            else:
                if building.country != item["country"]:
                    building.country = item["country"]
                    building.save(update_fields=["country", "updated_at"])

            person, person_created = Person.objects.update_or_create(
                email=item["email"],
                defaults={
                    "name": item["name"],
                    "company": item["company"],
                    "building": building,
                },
            )
            if person_created:
                created_people += 1
            else:
                updated_people += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded test leads: {created_people} created, {updated_people} updated, "
                f"{created_buildings} buildings created."
            )
        )
