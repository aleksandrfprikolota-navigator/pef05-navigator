from __future__ import annotations

import psycopg

from app.config import SQL_PATH, Settings


def connect(settings: Settings) -> psycopg.Connection:
    try:
        return psycopg.connect(settings.database_url, autocommit=True)
    except psycopg.OperationalError as exc:
        raise RuntimeError(
            "Нет соединения с PostgreSQL. Запустите базу: docker compose up -d db"
        ) from exc


def execute_script(conn: psycopg.Connection, script: str) -> None:
    for statement in script.split(";"):
        statement = statement.strip()
        if statement:
            conn.execute(statement)


def ensure_schema(conn: psycopg.Connection) -> None:
    execute_script(conn, SQL_PATH.read_text(encoding="utf-8"))
    for statement in (
        "DELETE FROM dialog_log WHERE created_at < now() - interval '90 days'",
        "DELETE FROM messages WHERE created_at < now() - interval '90 days'",
        "DELETE FROM api_usage WHERE created_at < now() - interval '90 days'",
        "DELETE FROM leads WHERE created_at < now() - interval '12 months'",
    ):
        conn.execute(statement)


def setting(conn: psycopg.Connection, key: str, default: str) -> str:
    row = conn.execute("SELECT value FROM settings WHERE key = %s", (key,)).fetchone()
    return row[0] if row else default


def set_setting(conn: psycopg.Connection, key: str, value: str) -> None:
    conn.execute(
        """
        INSERT INTO settings (key, value) VALUES (%s, %s)
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
        """,
        (key, value),
    )


def month_spend(conn: psycopg.Connection) -> float:
    row = conn.execute(
        """
        SELECT COALESCE(SUM(cost_usd), 0)
        FROM api_usage
        WHERE created_at >= date_trunc('month', now())
        """
    ).fetchone()
    return float(row[0])


def record_usage(
    conn: psycopg.Connection,
    *,
    kind: str,
    chat_id: int | None,
    input_tokens: int = 0,
    cached_tokens: int = 0,
    output_tokens: int = 0,
    embedding_tokens: int = 0,
    cost_usd: float = 0,
) -> None:
    conn.execute(
        """
        INSERT INTO api_usage (
            kind, chat_id, input_tokens, cached_tokens, output_tokens, embedding_tokens, cost_usd
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (kind, chat_id, input_tokens, cached_tokens, output_tokens, embedding_tokens, cost_usd),
    )


def spend_summary(conn: psycopg.Connection) -> dict:
    week = conn.execute(
        """
        SELECT
            COUNT(*) FILTER (WHERE NOT refused) AS answered,
            COUNT(*) FILTER (WHERE refused) AS refused,
            COALESCE(SUM(cost_usd), 0)
        FROM dialog_log
        WHERE created_at >= now() - interval '7 days'
        """
    ).fetchone()
    return {
        "answered_7d": int(week[0]),
        "refused_7d": int(week[1]),
        "cost_7d": float(week[2]),
        "cost_month": month_spend(conn),
    }


def index_version(conn: psycopg.Connection) -> str:
    row = conn.execute("SELECT version FROM index_meta WHERE id = 1").fetchone()
    return row[0] if row else "none"


def recent_messages(conn: psycopg.Connection, chat_id: int, limit: int = 6) -> list[dict]:
    rows = conn.execute(
        """
        SELECT role, content
        FROM messages
        WHERE chat_id = %s
        ORDER BY id DESC
        LIMIT %s
        """,
        (chat_id, limit),
    ).fetchall()
    return [{"role": role, "content": content} for role, content in reversed(rows)]


def add_message(conn: psycopg.Connection, chat_id: int, role: str, content: str) -> None:
    conn.execute(
        "INSERT INTO messages (chat_id, role, content) VALUES (%s, %s, %s)",
        (chat_id, role, content[:4000]),
    )


def log_dialog(conn: psycopg.Connection, **fields) -> None:
    conn.execute(
        """
        INSERT INTO dialog_log (
            chat_id, refused, source_urls, contour, input_tokens, cached_tokens,
            output_tokens, embedding_tokens, cost_usd, index_version, latency_ms
        )
        VALUES (%(chat_id)s, %(refused)s, %(source_urls)s, %(contour)s, %(input_tokens)s,
                %(cached_tokens)s, %(output_tokens)s, %(embedding_tokens)s, %(cost_usd)s,
                %(index_version)s, %(latency_ms)s)
        """,
        fields,
    )
