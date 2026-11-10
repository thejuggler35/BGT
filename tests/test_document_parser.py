import io
import unittest

import pymupdf
from docx import Document

from backend.document_parser import extract_text


class DocumentParserTests(unittest.TestCase):
    def test_extracts_pdf_text(self):
        document = pymupdf.open()
        document.new_page().insert_text((72, 72), "AURA Energy approved copy.")
        data = document.tobytes()
        document.close()

        text, source_type = extract_text("launch.pdf", data)

        self.assertEqual(source_type, "pdf")
        self.assertIn("AURA Energy approved copy.", text)

    def test_extracts_docx_paragraphs_and_tables(self):
        document = Document()
        document.add_paragraph("AURA Energy approved copy.")
        row = document.add_table(rows=1, cols=2).rows[0]
        row.cells[0].text = "AURA Zero"
        row.cells[1].text = "0 g added sugar"
        data = io.BytesIO()
        document.save(data)

        text, source_type = extract_text("launch.docx", data.getvalue())

        self.assertEqual(source_type, "docx")
        self.assertIn("AURA Energy approved copy.", text)
        self.assertIn("AURA Zero | 0 g added sugar", text)

    def test_rejects_mismatched_file_content(self):
        with self.assertRaisesRegex(ValueError, "valid PDF"):
            extract_text("draft.pdf", b"not a PDF")

    def test_rejects_invalid_docx_archive(self):
        with self.assertRaisesRegex(ValueError, "valid Word document"):
            extract_text("draft.docx", b"PK this is not a Word document")


if __name__ == "__main__":
    unittest.main()
