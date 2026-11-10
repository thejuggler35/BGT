import unittest

from backend.compliance import check_content
from backend.database import DEMO_RULES


class ComplianceTests(unittest.TestCase):
    def test_demo_draft_reports_evidence_linked_findings(self):
        draft = (
            "AURA Energy has 100mg caffeine per can and guaranteed results that cure fatigue all day. "
            "Try it NOW for an AMAZING boost!"
        )

        findings = check_content(draft, DEMO_RULES)
        categories = [finding["category"] for finding in findings]

        self.assertEqual(categories.count("restricted_term"), 2)
        self.assertIn("fact", categories)
        self.assertIn("preferred_term", categories)
        self.assertIn("tone", categories)
        fact = next(finding for finding in findings if finding["category"] == "fact")
        self.assertIn("80 mg", fact["evidence"])
        self.assertIn("100mg", fact["explanation"])

    def test_restricted_term_match_is_case_insensitive_and_word_bounded(self):
        findings = check_content(
            "The GUARANTEED RESULTS are noteworthy; nonguaranteed results are a different word.",
            DEMO_RULES,
        )
        matches = [finding for finding in findings if finding["category"] == "restricted_term"]

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["matched_text"], "GUARANTEED RESULTS")

    def test_preferred_language_is_a_suggestion_not_an_attention_flag(self):
        findings = check_content("A calm, clearly written draft.", DEMO_RULES)
        preferred = next(finding for finding in findings if finding["category"] == "preferred_term")

        self.assertEqual(preferred["severity"], "suggestion")


if __name__ == "__main__":
    unittest.main()
