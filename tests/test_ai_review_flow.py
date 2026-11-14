import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from backend import database, main
from backend.ai_analysis import AIAnalysisError


AI_FINDING = {
    "category": "ai_tone",
    "title": "Consider a clearer tone",
    "severity": "suggestion",
    "matched_text": "The original draft text.",
    "explanation": "The phrasing may not match the saved tone.",
    "evidence": "The sentence uses formal phrasing.",
    "guideline": "Brand voice",
    "suggestion": "Consider a more conversational phrase.",
}


class AIReviewFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "ai-review.sqlite3"
        self.database_patch = patch.object(database, "DATABASE_PATH", self.database_path)
        self.database_patch.start()
        database.initialize_database()
        self.actor = {"id": None, "name": "Workspace administrator", "role": "admin"}

    def tearDown(self):
        self.database_patch.stop()
        self.temp_dir.cleanup()

    def test_ai_opt_in_adds_findings_to_saved_review(self):
        with patch("backend.main.ai_analysis_enabled", return_value=True), patch(
            "backend.main.analyze_content", return_value=[AI_FINDING]
        ) as analyze:
            review = asyncio.run(main.create_review(
                text="The original draft text.",
                title="AI review",
                analyze_with_ai=True,
                file=None,
                actor=self.actor,
            ))

        analyze.assert_called_once()
        self.assertIn(AI_FINDING["category"], [finding["category"] for finding in review["findings"]])

    def test_rule_only_review_does_not_call_ai(self):
        with patch("backend.main.ai_analysis_enabled", return_value=True), patch(
            "backend.main.analyze_content"
        ) as analyze:
            review = asyncio.run(main.create_review(
                text="A draft to review.",
                title="Rule review",
                analyze_with_ai=False,
                file=None,
                actor=self.actor,
            ))

        analyze.assert_not_called()
        self.assertEqual(review["title"], "Rule review")

    def test_provider_failure_does_not_save_partial_review(self):
        with patch("backend.main.ai_analysis_enabled", return_value=True), patch(
            "backend.main.analyze_content",
            side_effect=AIAnalysisError("Provider unavailable."),
        ):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(main.create_review(
                    text="The original draft text.",
                    title="Failed AI review",
                    analyze_with_ai=True,
                    file=None,
                    actor=self.actor,
                ))

        self.assertEqual(raised.exception.status_code, 502)
        with database.connection() as conn:
            count = conn.execute("SELECT COUNT(*) AS count FROM reviews").fetchone()["count"]
        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
