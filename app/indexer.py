from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from app.allowlist import ALLOWLIST
from app.config import Settings, get_settings
from app.corpus import load_documents
from app.db import connect, ensure_schema
from app.textutil import api_cost_usd

logger = logging.getLogger(__name__)


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in values) + "]"


def _embed_batch(settings: Settings, texts: list[str]) -> tuple[list[list[float]], int]:
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url, timeout=60, max_retries=1)
    vectors: list[list[float]] = []
    tokens = 0
    for start in range(0, len(texts), 64):
        batch = texts[start : start + 64]
        response = client.embeddings.create(model=settings.embedding_model, input=batch)
        ordered = sorted(response.data, key=lambda item: item.index)
        vectors.extend(item.embedding for item in ordered)
        tokens += int(getattr(response.usage, "total_tokens", 0) or 0)
    return vectors, tokens


def _existing_embeddings(conn) -> dict[str, str]:
    rows = conn.execute("SELECT content_hash, embedding::text FROM chunks").fetchall()
    return {row[0]: row[1] for row in rows}


def touch_sources() -> list[tuple[str, str]]:
    results = []
    parsers: dict[str, RobotFileParser] = {}
    with httpx.Client(timeout=20, follow_redirects=True, headers={"User-Agent": "NavigatorBot/1.0"}) as client:
        for url in ALLOWLIST:
            origin = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
            if origin not in parsers:
                parser = RobotFileParser()
                parser.set_url(origin + "/robots.txt")
                try:
                    parser.read()
                except Exception:
                    parser.parse(["User-agent: *", "Allow: /"])
                parsers[origin] = parser
            if not parsers[origin].can_fetch("*", url):
                results.append((url, "robots.txt запрещает обход"))
                continue
            try:
                response = client.get(url)
                if response.status_code < 400:
                    results.append((url, "ok"))
                else:
                    results.append((url, f"HTTP {response.status_code}"))
            except Exception as exc:
                results.append((url, type(exc).__name__))
    return results


def rebuild_index(settings: Settings | None = None, touch: bool = True) -> dict:
    settings = settings or get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("В .env нет OPENAI_API_KEY")
    documents = load_documents()
    chunks = [chunk for document in documents for chunk in document["chunks"]]
    conn = connect(settings)
    ensure_schema(conn)
    known = _existing_embeddings(conn)
    missing = [chunk for chunk in chunks if chunk["content_hash"] not in known]
    fresh: dict[str, str] = {}
    embedding_tokens = 0
    if missing:
        vectors, embedding_tokens = _embed_batch(settings, [chunk["content"] for chunk in missing])
        fresh = {
            chunk["content_hash"]: _vector_literal(vector)
            for chunk, vector in zip(missing, vectors)
        }
        cost = api_cost_usd(0, 0, 0, embedding_tokens)
        conn.execute(
            """
            INSERT INTO api_usage (kind, embedding_tokens, cost_usd)
            VALUES ('reindex', %s, %s)
            """,
            (embedding_tokens, cost),
        )
    version_src = "|".join(sorted(chunk["content_hash"] for chunk in chunks)).encode("utf-8")
    version = hashlib.sha256(version_src).hexdigest()[:12]
    with conn.transaction():
        conn.execute("DELETE FROM chunks")
        conn.execute("DELETE FROM documents")
        for document in documents:
            conn.execute(
                """
                INSERT INTO documents (id, contour, source_url, title, captured, body_hash)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    document["id"],
                    document["contour"],
                    document["source_url"],
                    document["title"],
                    document["captured"],
                    hashlib.sha256(document["body"].encode("utf-8")).hexdigest(),
                ),
            )
        for chunk in chunks:
            embedding = fresh.get(chunk["content_hash"]) or known[chunk["content_hash"]]
            conn.execute(
                """
                INSERT INTO chunks (
                    doc_id, contour, source_url, heading_path, content,
                    content_hash, token_estimate, captured, embedding
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::vector)
                """,
                (
                    chunk["doc_id"],
                    chunk["contour"],
                    chunk["source_url"],
                    chunk["heading_path"],
                    chunk["content"],
                    chunk["content_hash"],
                    chunk["token_estimate"],
                    chunk["captured"],
                    embedding,
                ),
            )
        conn.execute(
            """
            INSERT INTO index_meta (id, version, built_at, chunk_count)
            VALUES (1, %s, now(), %s)
            ON CONFLICT (id) DO UPDATE
            SET version = EXCLUDED.version, built_at = now(), chunk_count = EXCLUDED.chunk_count
            """,
            (version, len(chunks)),
        )
    crawl_notes = []
    if touch:
        for url, status in touch_sources():
            crawl_notes.append(f"{url}: {status}")
            if status == "ok":
                conn.execute(
                    """
                    INSERT INTO crawl_status (source_url, last_success, last_error)
                    VALUES (%s, now(), NULL)
                    ON CONFLICT (source_url) DO UPDATE
                    SET last_success = now(), last_error = NULL
                    """,
                    (url,),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO crawl_status (source_url, last_error)
                    VALUES (%s, %s)
                    ON CONFLICT (source_url) DO UPDATE SET last_error = EXCLUDED.last_error
                    """,
                    (url, status),
                )
    else:
        captured = datetime.now(timezone.utc)
        for document in documents:
            conn.execute(
                """
                INSERT INTO crawl_status (source_url, last_success, last_error)
                VALUES (%s, %s, NULL)
                ON CONFLICT (source_url) DO NOTHING
                """,
                (document["source_url"], captured),
            )
    logger.info("index %s documents=%s chunks=%s new_embeddings=%s", version, len(documents), len(chunks), len(missing))
    return {
        "version": version,
        "documents": len(documents),
        "chunks": len(chunks),
        "embedded": len(missing),
        "embedding_tokens": embedding_tokens,
        "crawl": crawl_notes,
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    stats = rebuild_index()
    print(
        f"Индекс {stats['version']}: документов {stats['documents']}, "
        f"фрагментов {stats['chunks']}, новых эмбеддингов {stats['embedded']}"
    )


if __name__ == "__main__":
    main()
