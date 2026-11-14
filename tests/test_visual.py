import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

import pymupdf
from docx import Document
from PIL import Image, ImageDraw

from backend import database
from backend.database import DEMO_RULES, get_brand_rules, get_logo_reference, save_brand_rules
from backend.schemas import BrandRules
from backend.document_parser import extract_text
from backend.visual import analyze_visual_image, decode_image, extract_visual_images


def image_bytes(image, image_format="PNG"):
    output = io.BytesIO()
    image.save(output, format=image_format)
    return output.getvalue()


class VisualReviewTests(unittest.TestCase):
    def test_flags_dominant_off_palette_color_and_keeps_neutrals(self):
        image = Image.new("RGB", (240, 160), "#1769AA")
        image.paste("#FFFFFF", (0, 0, 40, 30))

        findings = analyze_visual_image(image, ["#FF0000"])

        color_findings = [finding for finding in findings if finding["category"] == "visual_color"]
        self.assertEqual(len(color_findings), 1)
        self.assertEqual(color_findings[0]["severity"], "suggestion")
        self.assertIn("#1769AA", color_findings[0]["matched_text"])

        compliant = analyze_visual_image(Image.new("RGB", (100, 100), "#FF0000"), ["#FF0000"])
        self.assertFalse(any(finding["category"] == "visual_color" for finding in compliant))

    def test_logo_reference_can_be_found_in_a_larger_visual(self):
        logo = Image.new("RGBA", (80, 60), (255, 255, 255, 0))
        draw = ImageDraw.Draw(logo)
        draw.polygon([(5, 5), (35, 5), (20, 28)], fill="#E21B54")
        draw.rectangle((42, 12, 72, 48), fill="#153A6B")
        target = Image.new("RGB", (320, 200), "#E9E9E9")
        target.paste(logo, (80, 50), logo.getchannel("A"))

        findings = analyze_visual_image(target, [], image_bytes(logo))

        self.assertEqual(findings[0]["category"], "visual_guidance")
        self.assertEqual(findings[1]["title"], "Reference logo likely present")

    def test_invalid_images_return_a_clear_error(self):
        with self.assertRaisesRegex(ValueError, "could not be decoded"):
            decode_image(b"not an image")

        with self.assertRaisesRegex(ValueError, "valid PNG"):
            extract_visual_images("draft.png", b"not an image")
        with self.assertRaisesRegex(ValueError, "does not match"):
            extract_visual_images("draft.png", image_bytes(Image.new("RGB", (10, 10)), "JPEG"))

    def test_large_images_are_downsampled_before_analysis(self):
        image = Image.new("RGB", (1600, 800), "#1769AA")

        decoded = decode_image(image_bytes(image))

        self.assertEqual(decoded.size, (1000, 500))

    def test_extracts_visuals_from_raster_pdf_and_docx(self):
        artwork = Image.new("RGB", (80, 60), "#1769AA")
        artwork_bytes = image_bytes(artwork)

        pdf = pymupdf.open()
        page = pdf.new_page(width=320, height=240)
        page.insert_image(pymupdf.Rect(30, 30, 290, 210), stream=artwork_bytes)
        pdf_bytes = pdf.tobytes()
        pdf.close()
        self.assertEqual(extract_text("campaign.pdf", pdf_bytes, allow_empty=True)[0], "")
        pdf_visuals, pdf_truncated = extract_visual_images("campaign.pdf", pdf_bytes)

        document = Document()
        document.add_paragraph("Campaign draft text.")
        document.add_picture(io.BytesIO(artwork_bytes))
        docx_output = io.BytesIO()
        document.save(docx_output)
        docx_visuals, docx_truncated = extract_visual_images("campaign.docx", docx_output.getvalue())

        self.assertEqual(len(pdf_visuals), 1)
        self.assertEqual(pdf_visuals[0][1], "PDF page 1")
        self.assertFalse(pdf_truncated)
        self.assertEqual(len(docx_visuals), 1)
        self.assertFalse(docx_truncated)

    def test_visual_guidelines_persist_without_returning_logo_binary(self):
        logo_data = image_bytes(Image.new("RGB", (32, 24), "#1769AA"))
        import base64

        rules = BrandRules(
            brand_name="Test brand",
            brand_voice=["Clear"],
            visual_palette=["#1769AA", "#FFFFFF"],
            logo_reference_data=f"data:image/png;base64,{base64.b64encode(logo_data).decode()}",
            logo_reference_name="test-logo.png",
            **{key: value for key, value in DEMO_RULES.items() if key not in {"brand_name", "brand_voice"}},
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "visual.sqlite3"
            with patch.object(database, "DATABASE_PATH", path):
                database.initialize_database()
                with database.connection() as conn:
                    save_brand_rules(conn, rules)
                with database.connection() as conn:
                    saved_rules = get_brand_rules(conn)
                    logo = get_logo_reference(conn)

        self.assertEqual(saved_rules["visual_palette"], ["#1769AA", "#FFFFFF"])
        self.assertEqual(saved_rules["logo_reference_name"], "test-logo.png")
        self.assertNotIn("logo_reference", saved_rules)
        self.assertEqual(bytes(logo["logo_reference"]), logo_data)


if __name__ == "__main__":
    unittest.main()
