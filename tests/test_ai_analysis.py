import io
import json
import os
import unittest
from urllib.error import HTTPError
from unittest.mock import patch

from backend.ai_analysis import (
    AIAnalysisError,
    ai_analysis_enabled,
    analyze_content,
    get_ai_settings,
)
from backend.database import DEMO_RULES


class AIAnalysisTests(unittest.TestCase):
    def test_analysis_is_disabled_without_provider_credentials(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(ai_analysis_enabled())

    def test_provider_settings_require_key_and_model(self):
        with patch.dict(os.environ, {"BGT_AI_API_KEY": "private-key"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "both BGT_AI_API_KEY and BGT_AI_MODEL"):
                get_ai_settings()

    def test_remote_http_provider_must_use_https(self):
        with patch.dict(os.environ, {
            "BGT_AI_API_KEY": "test-key",
            "BGT_AI_MODEL": "test-model",
            "BGT_AI_BASE_URL": "http://ai.example.test/v1",
        }, clear=True):
            with self.assertRaisesRegex(RuntimeError, "must be an HTTPS provider URL"):
                get_ai_settings()

    def test_draft_and_guidance_are_sent_only_to_the_configured_endpoint(self):
        draft = "A thoughtful example sentence."
        provider_result = {
            "findings": [{
                "category": "ai_tone",
                "title": "Consider a warmer tone",
                "severity": "suggestion",
                "matched_text": draft,
                "explanation": "The wording may sound more formal than the saved brand voice.",
                "evidence": "The sentence uses formal phrasing.",
                "guideline": "Brand voice: Friendly, Clear",
                "suggestion": "Consider a more conversational phrasing.",
            }]
        }
        response = io.BytesIO(json.dumps({
            "choices": [{"message": {"content": json.dumps(provider_result)}}]
        }).encode())
        settings = {
            "BGT_AI_API_KEY": "test-provider-key",
            "BGT_AI_MODEL": "test-model",
            "BGT_AI_BASE_URL": "https://ai.example.test/v1",
        }
        with patch.dict(os.environ, settings, clear=True), patch(
            "backend.ai_analysis.urlopen", return_value=response
        ) as open_url:
            findings = analyze_content(draft, DEMO_RULES)

        request = open_url.call_args.args[0]
        request_body = json.loads(request.data)
        submitted_context = json.loads(request_body["messages"][1]["content"])
        self.assertEqual(request.full_url, "https://ai.example.test/v1/chat/completions")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-provider-key")
        self.assertEqual(submitted_context["draft"], draft)
        self.assertEqual(request_body["model"], "test-model")
        self.assertEqual(findings[0]["category"], "ai_tone")
        self.assertEqual(findings[0]["matched_text"], draft)

    def test_invalid_provider_excerpt_is_rejected(self):
        draft = "The submitted sentence."
        provider_result = {
            "findings": [{
                "category": "ai_context",
                "title": "Unsupported quote",
                "severity": "suggestion",
                "matched_text": "This quote was not submitted.",
                "explanation": "This is a test.",
                "evidence": "",
                "guideline": "",
                "suggestion": "",
            }]
        }
        response = io.BytesIO(json.dumps({
            "choices": [{"message": {"content": json.dumps(provider_result)}}]
        }).encode())
        with patch.dict(os.environ, {
            "BGT_AI_API_KEY": "test-key",
            "BGT_AI_MODEL": "test-model",
        }, clear=True), patch("backend.ai_analysis.urlopen", return_value=response):
            with self.assertRaisesRegex(AIAnalysisError, "invalid finding"):
                analyze_content(draft, DEMO_RULES)

    def test_ai_character_limit_is_reported(self):
        with self.assertRaisesRegex(AIAnalysisError, "limited to 30,000 characters"):
            analyze_content("x" * 30_001, DEMO_RULES)

    def test_provider_http_errors_are_reported_without_response_body(self):
        error_body = io.BytesIO(b"private provider response")
        error = HTTPError(
            "https://ai.example.test/v1/chat/completions",
            401,
            "Unauthorized",
            {},
            error_body,
        )
        with patch.dict(os.environ, {
            "BGT_AI_API_KEY": "test-key",
            "BGT_AI_MODEL": "test-model",
        }, clear=True), patch("backend.ai_analysis.urlopen", side_effect=error):
            with self.assertRaisesRegex(AIAnalysisError, "HTTP 401") as raised:
                analyze_content("A draft sentence.", DEMO_RULES)
        error.close()
        self.assertNotIn("private provider response", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
