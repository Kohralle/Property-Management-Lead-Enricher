from __future__ import annotations

import re
from typing import TYPE_CHECKING

from rapidfuzz import fuzz

if TYPE_CHECKING:
    from leads.models import Person

FREE_EMAIL_PROVIDERS = frozenset({
    "gmail.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "aol.com",
    "icloud.com",
    "proton.me",
    "protonmail.com",
})

# Legal entity markers — stripped before descriptor words
_ENTITY_SUFFIXES = frozenset({
    "inc", "llc", "ltd", "corporation", "corp", "co", "company",
})
# Operational descriptors — stripped in a second pass to get the core name
_DESCRIPTOR_SUFFIXES = frozenset({
    "group", "holdings", "properties", "partners",
})
_ALL_SUFFIXES = _ENTITY_SUFFIXES | _DESCRIPTOR_SUFFIXES

_DOMAIN_MATCH_THRESHOLD = 70


def _to_words(text: str) -> list[str]:
    """Lowercase, collapse abbreviation dots (l.l.c. → llc), strip punctuation, split."""
    s = text.lower()
    # Remove dots between word characters so "l.l.c." becomes "llc" not "l l c"
    s = re.sub(r"(?<=\w)\.(?=\w)", "", s)
    s = re.sub(r"[^\w\s]", " ", s)
    return s.split()


def _strip_trailing(words: list[str], suffixes: frozenset[str]) -> list[str]:
    """Return copy of words with trailing suffix words removed (preserves sole word)."""
    words = list(words)
    while len(words) > 1 and words[-1] in suffixes:
        words.pop()
    return words


def _normalize(text: str) -> str:
    """
    Full normalization for fuzzy comparison:
      lowercase → strip punctuation → strip leading 'the' → strip all known suffixes.
    """
    if not text:
        return ""
    words = _to_words(text)
    if words and words[0] == "the":
        words = words[1:]
    words = _strip_trailing(words, _ALL_SUFFIXES)
    return " ".join(words)


def _company_query_variants(company: str) -> list[str]:
    """
    Return deduplicated query variants from most specific to most general:
      v1 – entity suffixes stripped, 'the' prefix retained, descriptors retained
      v2 – v1 without leading 'the'
      v3 – v2 with descriptor suffixes also stripped
    """
    if not company:
        return []
    words = _to_words(company)

    v1_words = _strip_trailing(words, _ENTITY_SUFFIXES)
    v1 = " ".join(v1_words)

    v2_words = v1_words[1:] if v1_words and v1_words[0] == "the" else v1_words
    v2 = " ".join(v2_words)

    v3_words = _strip_trailing(v2_words, _DESCRIPTOR_SUFFIXES)
    v3 = " ".join(v3_words)

    seen: set[str] = set()
    variants: list[str] = []
    for v in (v1, v2, v3):
        if v and v not in seen:
            seen.add(v)
            variants.append(v)
    return variants


def parse_lead(lead: Person) -> dict:
    email_local, email_domain = lead.email.split("@", 1)
    email_domain = email_domain.lower()

    normalized_domain = _normalize(email_domain)
    normalized_company = _normalize(lead.company or "")

    domain_matches = bool(
        normalized_company
        and fuzz.ratio(normalized_domain, normalized_company) >= _DOMAIN_MATCH_THRESHOLD
    )

    return {
        "email_local": email_local,
        "email_domain": email_domain,
        "is_free_email_provider": email_domain in FREE_EMAIL_PROVIDERS,
        "domain_matches_company": domain_matches,
        "company_query_variants": _company_query_variants(lead.company or ""),
    }
