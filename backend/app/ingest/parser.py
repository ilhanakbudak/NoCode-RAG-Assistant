# backend/app/ingest/parser.py

import fitz
import docx
from pathlib import Path

def load_file_text(file_path: Path) -> str:
    if file_path.suffix == ".pdf":
        doc = fitz.open(file_path)
        return " ".join(page.get_text() for page in doc)
    elif file_path.suffix == ".docx":
        doc = docx.Document(file_path)
        return " ".join(p.text for p in doc.paragraphs)
    elif file_path.suffix == ".txt":
        return file_path.read_text()
    else:
        raise ValueError("Unsupported file type")