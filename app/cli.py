"""Консольный вопрос без Telegram: python -m app.cli \"текст вопроса\"."""

from __future__ import annotations

import sys

from app.answer import answer_question
from app.config import get_settings
from app.db import connect, ensure_schema, recent_messages


def main() -> None:
    question = " ".join(sys.argv[1:]).strip()
    if not question:
        print("Передайте вопрос аргументом.")
        return
    settings = get_settings()
    conn = connect(settings)
    ensure_schema(conn)
    history = recent_messages(conn, 1)
    result = answer_question(conn, settings, 1, question, history)
    print(result.text)
    print(f"\n[refused={result.refused} cost={result.cost_usd:.4f} USD]")


if __name__ == "__main__":
    main()
