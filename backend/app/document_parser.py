from pathlib import Path

import fitz
from docx import Document


def extract_pdf_text(file_path: str) -> str:
    document = fitz.open(file_path)

    pages = []

    for page_number, page in enumerate(document, start=1):
        text = page.get_text()

        pages.append(
            f"\n--- Page {page_number} ---\n{text}"
        )

    document.close()

    return "\n".join(pages)


def extract_docx_text(file_path: str) -> str:
    document = Document(file_path)

    paragraphs = []

    for paragraph in document.paragraphs:
        if paragraph.text.strip():
            paragraphs.append(paragraph.text)

    return "\n".join(paragraphs)


def extract_text(file_path: str) -> str:
    extension = Path(file_path).suffix.lower()

    if extension == ".pdf":
        return extract_pdf_text(file_path)

    if extension == ".docx":
        return extract_docx_text(file_path)

    raise ValueError(
        "Unsupported file format. Only PDF and DOCX are supported."
    )