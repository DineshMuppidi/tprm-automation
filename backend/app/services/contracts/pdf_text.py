"""Extracts raw text from an uploaded contract file. PDF via pypdf (pure
Python, no system dependencies — same reasoning as reportlab in Phase 1);
anything else is treated as plain text."""

import io

from pypdf import PdfReader


def extract_text(filename: str, content: bytes) -> str:
    if filename.lower().endswith(".pdf"):
        reader = PdfReader(io.BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return content.decode("utf-8", errors="ignore")
