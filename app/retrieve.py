from __future__ import annotations

from dataclasses import dataclass

import psycopg

from app.textutil import reciprocal_rank_fusion


@dataclass
class Hit:
    chunk_id: str
    contour: str
    source_url: str
    heading_path: str
    content: str
    similarity: float
    token_estimate: int


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in values) + "]"


def _or_tsquery(conn: psycopg.Connection, text: str) -> str | None:
    row = conn.execute(
        """
        SELECT string_agg(lexeme, ' | ')
        FROM unnest(to_tsvector('russian', %s)) AS lex(lexeme, positions, weights)
        """,
        (text,),
    ).fetchone()
    if not row or not row[0]:
        return None
    return row[0]


def search(conn: psycopg.Connection, embedding: list[float], question: str, contour: str) -> tuple[list[Hit], float]:
    literal = _vector_literal(embedding)
    contour_sql = ""
    params: list = [literal]
    if contour in {"personal", "premium"}:
        contour_sql = "AND contour = %s"
        params.append(contour)
    params.append(literal)
    vector_rows = conn.execute(
        f"""
        SELECT id::text, contour, source_url, heading_path, content,
               1 - (embedding <=> %s::vector) AS similarity, token_estimate
        FROM chunks
        WHERE true {contour_sql}
        ORDER BY embedding <=> %s::vector
        LIMIT 20
        """,
        params,
    ).fetchall()
    best = float(vector_rows[0][5]) if vector_rows else 0.0
    or_query = _or_tsquery(conn, question)
    fts_rows = []
    if or_query:
        fts_params: list = [literal, or_query]
        fts_sql = ""
        if contour in {"personal", "premium"}:
            fts_sql = "AND contour = %s"
            fts_params.append(contour)
        fts_params.append(or_query)
        try:
            fts_rows = conn.execute(
                f"""
                SELECT id::text, contour, source_url, heading_path, content, token_estimate,
                       1 - (embedding <=> %s::vector) AS similarity
                FROM chunks
                WHERE tsv @@ to_tsquery('russian', %s)
                {fts_sql}
                ORDER BY ts_rank_cd(tsv, to_tsquery('russian', %s)) DESC
                LIMIT 20
                """,
                fts_params,
            ).fetchall()
        except psycopg.Error:
            fts_rows = []

    by_id: dict[str, Hit] = {}
    vector_order: list[str] = []
    for row in vector_rows:
        hit = Hit(row[0], row[1], row[2], row[3], row[4], float(row[5]), int(row[6]))
        by_id[hit.chunk_id] = hit
        vector_order.append(hit.chunk_id)
    fts_order: list[str] = []
    for row in fts_rows:
        chunk_id = row[0]
        fts_order.append(chunk_id)
        if chunk_id not in by_id:
            by_id[chunk_id] = Hit(row[0], row[1], row[2], row[3], row[4], float(row[6]), int(row[5]))
    fused = reciprocal_rank_fusion([vector_order, fts_order])
    selected: list[Hit] = []
    tokens = 0
    for chunk_id in fused:
        hit = by_id[chunk_id]
        if len(selected) >= 5:
            break
        if selected and tokens + hit.token_estimate > 3500:
            continue
        selected.append(hit)
        tokens += hit.token_estimate
    return selected, best
