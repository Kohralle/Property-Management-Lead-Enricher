import unittest
from types import SimpleNamespace

from leads.enrichment.services.parsing import (
    _normalize,
    _company_query_variants,
    parse_lead,
)


def lead(email: str, company: str = "") -> SimpleNamespace:
    return SimpleNamespace(email=email, company=company)


class TestParseLeadFields(unittest.TestCase):
    def test_email_split(self):
        result = parse_lead(lead("jane@bozzuto.com", "Bozzuto Group"))
        self.assertEqual(result["email_local"], "jane")
        self.assertEqual(result["email_domain"], "bozzuto.com")

    def test_email_domain_lowercased(self):
        result = parse_lead(lead("Jane@Bozzuto.COM", "Bozzuto Group"))
        self.assertEqual(result["email_domain"], "bozzuto.com")


class TestFreeEmailProvider(unittest.TestCase):
    def test_gmail_is_free(self):
        result = parse_lead(lead("bob@gmail.com", "Some Corp"))
        self.assertTrue(result["is_free_email_provider"])

    def test_yahoo_is_free(self):
        result = parse_lead(lead("bob@yahoo.com", "Some Corp"))
        self.assertTrue(result["is_free_email_provider"])

    def test_hotmail_is_free(self):
        result = parse_lead(lead("bob@hotmail.com"))
        self.assertTrue(result["is_free_email_provider"])

    def test_outlook_is_free(self):
        result = parse_lead(lead("bob@outlook.com"))
        self.assertTrue(result["is_free_email_provider"])

    def test_proton_me_is_free(self):
        result = parse_lead(lead("bob@proton.me"))
        self.assertTrue(result["is_free_email_provider"])

    def test_protonmail_is_free(self):
        result = parse_lead(lead("bob@protonmail.com"))
        self.assertTrue(result["is_free_email_provider"])

    def test_corporate_is_not_free(self):
        result = parse_lead(lead("jane@bozzuto.com", "The Bozzuto Group, Inc."))
        self.assertFalse(result["is_free_email_provider"])


class TestDomainMatchesCompany(unittest.TestCase):
    def test_matching_domain_and_company(self):
        result = parse_lead(lead("jane@bozzuto.com", "The Bozzuto Group, Inc."))
        self.assertTrue(result["domain_matches_company"])

    def test_exact_single_word_match(self):
        result = parse_lead(lead("alice@greystar.com", "Greystar"))
        self.assertTrue(result["domain_matches_company"])

    def test_domain_mismatch(self):
        result = parse_lead(lead("alice@microsoft.com", "Bozzuto Group"))
        self.assertFalse(result["domain_matches_company"])

    def test_free_email_does_not_match_company(self):
        result = parse_lead(lead("bob@gmail.com", "Acme Corp"))
        self.assertFalse(result["domain_matches_company"])

    def test_no_company_is_no_match(self):
        result = parse_lead(lead("bob@gmail.com", ""))
        self.assertFalse(result["domain_matches_company"])


class TestNormalize(unittest.TestCase):
    def test_strips_inc(self):
        self.assertEqual(_normalize("Acme Inc."), "acme")

    def test_strips_llc(self):
        self.assertEqual(_normalize("Acme L.L.C."), "acme")

    def test_strips_group(self):
        self.assertEqual(_normalize("Bozzuto Group"), "bozzuto")

    def test_strips_leading_the(self):
        self.assertEqual(_normalize("The Bozzuto Group, Inc."), "bozzuto")

    def test_preserves_sole_word(self):
        self.assertEqual(_normalize("Greystar"), "greystar")

    def test_strips_multiple_suffixes(self):
        self.assertEqual(_normalize("Lincoln Properties, Inc."), "lincoln")

    def test_collapses_whitespace(self):
        self.assertEqual(_normalize("  Acme   Corp  "), "acme")


class TestCompanyQueryVariants(unittest.TestCase):
    def test_bozzuto_group_inc_minimum_variants(self):
        variants = _company_query_variants("The Bozzuto Group, Inc.")
        self.assertIn("bozzuto group", variants)
        self.assertIn("bozzuto", variants)

    def test_bozzuto_group_inc_full_variants(self):
        variants = _company_query_variants("The Bozzuto Group, Inc.")
        self.assertEqual(variants, ["the bozzuto group", "bozzuto group", "bozzuto"])

    def test_single_word_greystar(self):
        variants = _company_query_variants("Greystar")
        self.assertEqual(variants, ["greystar"])

    def test_no_duplicates(self):
        variants = _company_query_variants("Greystar")
        self.assertEqual(len(variants), len(set(variants)))

    def test_empty_company(self):
        self.assertEqual(_company_query_variants(""), [])

    def test_entity_suffix_only_stripped_in_v1(self):
        # "Lincoln Properties Inc" → v1 strips inc, v2 strips the (none), v3 strips properties
        variants = _company_query_variants("Lincoln Properties, Inc.")
        self.assertEqual(variants[0], "lincoln properties")
        self.assertEqual(variants[-1], "lincoln")

    def test_order_most_specific_first(self):
        variants = _company_query_variants("The Bozzuto Group, Inc.")
        # "the bozzuto group" is longer/more specific than "bozzuto"
        self.assertGreater(len(variants[0]), len(variants[-1]))

    def test_via_parse_lead(self):
        result = parse_lead(lead("jane@bozzuto.com", "The Bozzuto Group, Inc."))
        self.assertIn("bozzuto group", result["company_query_variants"])
        self.assertIn("bozzuto", result["company_query_variants"])


if __name__ == "__main__":
    unittest.main()
