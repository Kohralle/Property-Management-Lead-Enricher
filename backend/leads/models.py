from django.db import models


class Building(models.Model):
    property_address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100, default='USA')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.property_address}, {self.city}, {self.state}"


class Person(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    company = models.CharField(max_length=255, blank=True)
    building = models.ForeignKey(
        Building, on_delete=models.SET_NULL, null=True, blank=True, related_name='contacts'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.email})"


class EnrichmentResult(models.Model):
    SCORE_TIER_CHOICES = [("A", "A"), ("B", "B"), ("C", "C"), ("D", "D")]

    lead = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="enrichments")
    score_total = models.PositiveIntegerField(default=0)
    score_tier = models.CharField(max_length=1, choices=SCORE_TIER_CHOICES)
    score_breakdown = models.JSONField()
    email_subject = models.TextField(blank=True)
    email_body = models.TextField(blank=True)
    insights = models.JSONField(default=list)
    raw_enrichment = models.JSONField(default=dict)
    disqualifier_flag = models.BooleanField(default=False)
    disqualifier_reason = models.TextField(blank=True)
    llm_reasoning = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.lead} — {self.score_tier} ({self.score_total})"
