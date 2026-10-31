from __future__ import annotations

from pathlib import Path

from app.config import KNOWLEDGE_DIR
from app.textutil import build_chunks, parse_markdown


def load_documents(directory: Path | None = None) -> list[dict]:
    root = directory or KNOWLEDGE_DIR
    documents = []
    for path in sorted(root.glob("*.md")):
        meta, body = parse_markdown(path.read_text(encoding="utf-8"))
        doc_id = meta.get("id") or path.stem
        contour = meta.get("contour", "")
        url = meta.get("source_url", "")
        if contour not in {"personal", "premium"} or not url:
            raise ValueError(f"{path.name}: нужны contour и source_url")
        documents.append(
            {
                "id": doc_id,
                "contour": contour,
                "source_url": url,
                "title": meta.get("title", path.stem),
                "captured": meta.get("captured", ""),
                "body": body.strip(),
                "chunks": build_chunks(doc_id, contour, url, meta.get("captured", ""), body),
            }
        )
    return documents
