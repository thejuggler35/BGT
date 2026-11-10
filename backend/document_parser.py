from io import BytesIO
from zipfile import ZipFile

import pymupdf
from docx import Document


MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_PDF_PAGES = 250
MAX_DOCX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024


def extract_text(filename, content):
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix == "pdf":
        if not content.startswith(b"%PDF-"):
            raise ValueError("This file is not a valid PDF document.")
        try:
            document = pymupdf.open(stream=content, filetype="pdf")
        except Exception as exc:
            raise ValueError("This PDF could not be read. Check that it is a valid, text-based PDF.") from exc
        with document:
            if len(document) > MAX_PDF_PAGES:
                raise ValueError(f"PDFs must contain {MAX_PDF_PAGES} pages or fewer.")
            try:
                text = "\n".join(page.get_text() for page in document)
            except Exception as exc:
                raise ValueError("This PDF could not be read. Check that it is a valid, text-based PDF.") from exc
        if not text.strip():
            raise ValueError("No readable text was found in the PDF. Scanned image PDFs are not supported yet.")
        return text, "pdf"
    if suffix == "docx":
        if not content.startswith(b"PK"):
            raise ValueError("This file is not a valid DOCX document.")
        try:
            with ZipFile(BytesIO(content)) as archive:
                expanded_size = sum(item.file_size for item in archive.infolist())
        except Exception as exc:
            raise ValueError("This DOCX could not be read. Check that it is a valid Word document.") from exc
        if expanded_size > MAX_DOCX_UNCOMPRESSED_BYTES:
            raise ValueError("This DOCX expands beyond the 50 MB processing limit.")
        try:
            document = Document(BytesIO(content))
            paragraphs = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
            for table in document.tables:
                for row in table.rows:
                    paragraphs.append(" | ".join(cell.text for cell in row.cells))
            text = "\n".join(paragraphs)
        except Exception as exc:
            raise ValueError("This DOCX could not be read. Check that it is a valid Word document.") from exc
        if not text.strip():
            raise ValueError("No readable text was found in the DOCX.")
        return text, "docx"
    raise ValueError("Unsupported file type. Upload a PDF or DOCX document.")
