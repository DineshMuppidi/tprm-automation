"""Evidence file storage.

Local filesystem by default, keyed the same way an S3 object would be
(`{assessment_id}/{uuid}_{filename}`) so swapping in a real S3-backed
implementation later is a matter of implementing this same interface, not
reshaping how callers use it.
"""

import uuid
from pathlib import Path

from app.config import get_settings


def _root() -> Path:
    root = Path(get_settings().storage_root)
    root.mkdir(parents=True, exist_ok=True)
    return root


def save_evidence_file(assessment_id: str, filename: str, content: bytes) -> str:
    """Returns a storage_uri (relative path) to persist on the evidence row."""
    safe_name = filename.replace("/", "_").replace("\\", "_")
    key = f"{assessment_id}/{uuid.uuid4().hex}_{safe_name}"
    path = _root() / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return key


def read_evidence_file(storage_uri: str) -> bytes:
    path = _root() / storage_uri
    return path.read_bytes()


def infer_document_type(filename: str, declared: str | None) -> str:
    if declared:
        return declared
    lower = filename.lower()
    if "soc2" in lower or "soc 2" in lower:
        return "soc2_type2" if "type ii" in lower or "type2" in lower or "type 2" in lower else "soc2_type1"
    if "iso27001" in lower or "iso 27001" in lower:
        return "iso27001_cert"
    if lower.endswith((".png", ".jpg", ".jpeg")):
        return "screenshot"
    return "other"
