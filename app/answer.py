from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from openai import OpenAI

from app.allowlist import BUDGET_STOP, REFUSAL, UNAVAILABLE
from app.config import PROMPT_PATH, Settings
from app.db import index_version, log_dialog, month_spend, record_usage, setting
from app.retrieve import Hit, search
from app.textutil import (
    api_cost_usd,
    detect_contour,
    is_refusal_text,
    mask_contacts,
    price_is_grounded,
    strip_markup,
    trim_sources,
    wants_english,
)

logger = logging.getLogger(__name__)


@dataclass
class AnswerResult:
    text: str
    refused: bool
    warn_owner: bool
    cost_usd: float


def _prompt_parts() -> tuple[str, str]:
    template = PROMPT_PATH.read_text(encoding="utf-8")
    head, rest = template.split("КОНТЕКСТ", 1)
    _unused, rest = rest.split("ВОПРОС", 1)
    _question, form = rest.split("ФОРМАТ", 1)
    return head.strip() + "\n\nФОРМАТ\n" + form.strip(), form.strip()


def _format_hits(hits: list[Hit]) -> str:
    blocks = []
    for index, hit in enumerate(hits, start=1):
        contour_name = "личная практика" if hit.contour == "personal" else "ООО «1С-Премиум»"
        blocks.append(
            f"[{index}] контур: {hit.contour} ({contour_name})\n"
            f"путь: {hit.heading_path}\n"
            f"url: {hit.source_url}\n"
            f"{hit.content}"
        )
    return "\n\n".join(blocks)


def _admits_gap(text: str) -> bool:
    folded = text.casefold().replace("ё", "е")
    if "во фрагментах нет" in folded or "фрагменты не содержат" in folded:
        return True
    if "лиценз" in folded and ("не указан" in folded or "не могу" in folded):
        return True
    return False


def _usage(response) -> tuple[int, int, int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0, 0, 0
    details = getattr(usage, "input_tokens_details", None)
    cached = int(getattr(details, "cached_tokens", 0) or 0) if details is not None else 0
    return (
        int(getattr(usage, "input_tokens", 0) or 0),
        cached,
        int(getattr(usage, "output_tokens", 0) or 0),
    )


def _client(settings: Settings, timeout: float) -> OpenAI:
    return OpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        timeout=timeout,
        max_retries=0,
    )


def answer_question(
    conn,
    settings: Settings,
    chat_id: int,
    question: str,
    history: list[dict] | None = None,
) -> AnswerResult:
    started = time.perf_counter()
    version = index_version(conn)
    spend = month_spend(conn)
    warn = False
    month_key = time.strftime("warn80_%Y-%m")
    if spend >= settings.warn_budget_usd and setting(conn, month_key, "0") != "1":
        warn = True
        from app.db import set_setting

        set_setting(conn, month_key, "1")
    if setting(conn, "generation_enabled", "1") != "1" or spend >= settings.monthly_budget_usd:
        text = BUDGET_STOP
        _store(conn, chat_id, question, text, True, "", "none", 0, 0, 0, 0, 0, version, started)
        return AnswerResult(text, True, warn, 0)

    count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    if count == 0:
        text = "Индекс базы ещё не собран. Нужна команда владельца /reindex."
        return AnswerResult(text, True, warn, 0)

    masked = mask_contacts(question.strip())
    contour = detect_contour(masked)
    try:
        embed_response = _client(settings, 20).embeddings.create(
            model=settings.embedding_model,
            input=masked,
        )
    except Exception:
        logger.exception("embedding failed")
        _store(conn, chat_id, masked, UNAVAILABLE, True, "", contour, 0, 0, 0, 0, 0, version, started)
        return AnswerResult(UNAVAILABLE, True, warn, 0)
    embedding_tokens = int(getattr(embed_response.usage, "total_tokens", 0) or 0)
    embedding = embed_response.data[0].embedding
    embed_cost = api_cost_usd(0, 0, 0, embedding_tokens)
    record_usage(conn, kind="query_embedding", chat_id=chat_id, embedding_tokens=embedding_tokens, cost_usd=embed_cost)

    hits, best = search(conn, embedding, masked, contour)
    if not hits or best < settings.similarity_threshold:
        _store(
            conn, chat_id, masked, REFUSAL, True, "", contour,
            0, 0, 0, embedding_tokens, embed_cost, version, started,
        )
        return AnswerResult(REFUSAL, True, warn, embed_cost)

    instructions, _form = _prompt_parts()
    question_for_model = masked
    if wants_english(masked):
        question_for_model += "\nОтветь на английском языке. Факты те же."
    user_block = f"КОНТЕКСТ\n{_format_hits(hits)}\n\nВОПРОС\n{question_for_model}"
    prior = []
    for item in (history or [])[-6:]:
        if item["role"] in {"user", "assistant"}:
            prior.append({"role": item["role"], "content": item["content"][:1500]})
    try:
        response = _client(settings, 25).responses.create(
            model=settings.openai_model,
            instructions=instructions,
            reasoning={"effort": settings.reasoning_effort},
            input=prior + [{"role": "user", "content": user_block}],
        )
        raw = strip_markup(getattr(response, "output_text", "") or "")
    except Exception:
        logger.exception("response failed")
        _store(
            conn, chat_id, masked, UNAVAILABLE, True, "", contour,
            0, 0, 0, embedding_tokens, embed_cost, version, started,
        )
        return AnswerResult(UNAVAILABLE, True, warn, embed_cost)

    input_tokens, cached_tokens, output_tokens = _usage(response)
    model_cost = api_cost_usd(input_tokens, cached_tokens, output_tokens, 0)
    record_usage(
        conn,
        kind="answer",
        chat_id=chat_id,
        input_tokens=input_tokens,
        cached_tokens=cached_tokens,
        output_tokens=output_tokens,
        cost_usd=model_cost,
    )
    total = embed_cost + model_cost
    personal = [hit.content for hit in hits if hit.contour == "personal"]
    urls: list[str] = []
    for hit in hits:
        if hit.source_url not in urls:
            urls.append(hit.source_url)
    refused = False
    if not raw or not price_is_grounded(raw, personal):
        text = REFUSAL
        refused = True
    elif is_refusal_text(raw) or _admits_gap(raw):
        text = REFUSAL
        refused = True
    else:
        text = trim_sources(raw, urls[:3], refusal=False)
    _store(
        conn, chat_id, masked, text, refused, ", ".join(urls[:3]), contour,
        input_tokens, cached_tokens, output_tokens, embedding_tokens, total, version, started,
    )
    return AnswerResult(text, refused, warn or month_spend(conn) >= settings.warn_budget_usd, total)


def _store(
    conn,
    chat_id: int,
    question: str,
    answer: str,
    refused: bool,
    urls: str,
    contour: str,
    input_tokens: int,
    cached_tokens: int,
    output_tokens: int,
    embedding_tokens: int,
    cost: float,
    version: str,
    started: float,
) -> None:
    from app.db import add_message

    if chat_id:
        add_message(conn, chat_id, "user", question)
        add_message(conn, chat_id, "assistant", answer)
    log_dialog(
        conn,
        chat_id=chat_id,
        refused=refused,
        source_urls=urls,
        contour=contour,
        input_tokens=input_tokens,
        cached_tokens=cached_tokens,
        output_tokens=output_tokens,
        embedding_tokens=embedding_tokens,
        cost_usd=cost,
        index_version=version,
        latency_ms=int((time.perf_counter() - started) * 1000),
    )
