from __future__ import annotations

import hashlib
import re

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(
    r"(?:(?:\+7|8)[\s\-(]*\d{3}[\s\-)]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}|\+\d{11,15})"
)
CURRENCY_RE = re.compile(r"(₽|руб(?:\.|лей|ля|ль)?|usd|долл(?:аров|ара)?|\$)", re.IGNORECASE)
NUMBER_RE = re.compile(r"\d{1,3}(?:[ \u00a0]\d{3})+|\d+")
HEADING_RE = re.compile(r"^(#{1,3})\s+(.+?)\s*$")
FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
URL_RE = re.compile(r"https?://[^\s<>)\]]+")

PERSONAL_MARKERS = (
    "консультац",
    "оферт",
    "знакомств",
    "ipma",
    "резюме",
    "формат работ",
    "юkassa",
    "юкасса",
    "komfortnavigator",
    "комфортнавигатор",
    "первая встреч",
)
PREMIUM_MARKERS = (
    "1с-премиум",
    "1с премиум",
    "1c-prem",
    "1c prem",
    "кптр",
    "шина",
    "вайбкодинг",
    "центр компетенц",
    "corp@",
    "инцидент",
    "производительн",
    "мониторинг",
    "премиальн",
)
BOTH_WITH_PREMIUM = ("работа", "сейчас", "резюме", "александр", "консультац")


def estimate_tokens(text: str) -> int:
    return max(1, int(len(text) / 2.5))


def content_hash(contour: str, url: str, heading: str, text: str) -> str:
    payload = f"{contour}|{url}|{heading}|{text}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def mask_contacts(text: str) -> str:
    masked = EMAIL_RE.sub("[email]", text)
    return PHONE_RE.sub("[телефон]", masked)


def normalize_question(text: str) -> str:
    return text.casefold().replace("ё", "е")


def detect_contour(question: str) -> str:
    folded = normalize_question(question)
    personal = any(marker in folded for marker in PERSONAL_MARKERS)
    premium = any(marker in folded for marker in PREMIUM_MARKERS)
    if personal and premium:
        return "both"
    if premium and any(word in folded for word in BOTH_WITH_PREMIUM):
        return "both"
    if personal:
        return "personal"
    if premium:
        return "premium"
    return "both"


def _digits(token: str) -> str:
    return re.sub(r"\D", "", token)


def money_amounts(text: str) -> set[str]:
    found: set[str] = set()
    for match in CURRENCY_RE.finditer(text):
        window = text[max(0, match.start() - 48) : match.end()]
        for number in NUMBER_RE.finditer(window):
            digits = _digits(number.group())
            if len(digits) >= 3:
                found.add(digits)
    return found


def numbers_in_text(text: str) -> set[str]:
    return {_digits(item.group()) for item in NUMBER_RE.finditer(text) if _digits(item.group())}


def price_is_grounded(answer: str, personal_texts: list[str]) -> bool:
    claimed = money_amounts(answer)
    if not claimed:
        return True
    allowed: set[str] = set()
    for text in personal_texts:
        allowed.update(numbers_in_text(text))
    return claimed <= allowed


def reciprocal_rank_fusion(ranked_ids: list[list[str]], k: int = 60) -> list[str]:
    scores: dict[str, float] = {}
    for sequence in ranked_ids:
        for rank, item_id in enumerate(sequence, start=1):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank)
    return [item_id for item_id, _score in sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))]


def parse_markdown(text: str) -> tuple[dict[str, str], str]:
    match = FRONT_MATTER_RE.match(text)
    if not match:
        return {}, text
    meta: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip()
    return meta, text[match.end() :]


def is_protected(heading_path: str, text: str) -> bool:
    blob = f"{heading_path}\n{text[:500]}".casefold().replace("ё", "е")
    return "стоимость:" in blob or "оферт" in blob


def split_sections(body: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    stack: list[tuple[int, str]] = []
    buffer: list[str] = []
    current_path = ""

    def flush() -> None:
        content = "\n".join(buffer).strip()
        if content:
            sections.append((current_path or "Документ", content))

    for line in body.splitlines():
        heading = HEADING_RE.match(line)
        if heading:
            flush()
            buffer = []
            level = len(heading.group(1))
            title = heading.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            current_path = " / ".join(item[1] for item in stack)
            buffer.append(line)
            continue
        buffer.append(line)
    flush()
    return sections


def _split_large(text: str, limit: int = 800, overlap_tokens: int = 80) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    if estimate_tokens(text) <= limit or len(paragraphs) < 2:
        return [text.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0
    for paragraph in paragraphs:
        paragraph_tokens = estimate_tokens(paragraph)
        if current and current_tokens + paragraph_tokens > limit:
            chunks.append("\n\n".join(current))
            tail: list[str] = []
            tail_tokens = 0
            for previous in reversed(current):
                tail.append(previous)
                tail_tokens += estimate_tokens(previous)
                if tail_tokens >= overlap_tokens:
                    break
            current = list(reversed(tail))
            current_tokens = sum(estimate_tokens(part) for part in current)
        current.append(paragraph)
        current_tokens += paragraph_tokens
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def build_chunks(doc_id: str, contour: str, url: str, captured: str, body: str) -> list[dict]:
    pieces: list[tuple[str, str, bool]] = []
    for heading, text in split_sections(body):
        protected = is_protected(heading, text)
        parts = [text] if protected else _split_large(text)
        for part in parts:
            pieces.append((heading, part, protected))

    merged: list[tuple[str, str]] = []
    index = 0
    while index < len(pieces):
        heading, text, protected = pieces[index]
        if protected or estimate_tokens(text) >= 400 or index == len(pieces) - 1:
            merged.append((heading, text))
            index += 1
            continue
        combined_heading = heading
        combined_text = text
        index += 1
        while index < len(pieces):
            next_heading, next_text, next_protected = pieces[index]
            if next_protected:
                break
            candidate = combined_text + "\n\n" + next_text
            if estimate_tokens(candidate) > 800:
                break
            combined_text = candidate
            combined_heading = combined_heading if combined_heading == next_heading else f"{combined_heading} + {next_heading}"
            index += 1
            if estimate_tokens(combined_text) >= 400:
                break
        merged.append((combined_heading, combined_text))

    result = []
    for heading, text in merged:
        result.append(
            {
                "doc_id": doc_id,
                "contour": contour,
                "source_url": url,
                "heading_path": heading,
                "content": text,
                "captured": captured,
                "token_estimate": estimate_tokens(text),
                "content_hash": content_hash(contour, url, heading, text),
            }
        )
    return result


def wants_english(text: str) -> bool:
    letters = [char for char in text if char.isalpha()]
    if len(letters) < 8:
        return False
    cyrillic = sum(1 for char in letters if "а" <= char.casefold() <= "я" or char.casefold() == "ё")
    return cyrillic / len(letters) < 0.25


def strip_markup(text: str) -> str:
    cleaned = re.sub(r"<[^>]+>", "", text)
    cleaned = cleaned.replace("**", "").replace("__", "")
    cleaned = re.sub(r"```.*?```", "", cleaned, flags=re.DOTALL)
    return cleaned.strip()


def is_refusal_text(text: str) -> bool:
    folded = text.casefold().replace("ё", "е")
    return "нет достаточных сведений" in folded or "не буду додумывать" in folded


def trim_sources(text: str, allowed_urls: list[str], refusal: bool) -> str:
    body = URL_RE.sub("", text).strip() if refusal else text.strip()
    if refusal:
        return body
    found: list[str] = []
    for match in URL_RE.finditer(text):
        url = match.group(0).rstrip(".,);")
        if url in allowed_urls and url not in found:
            found.append(url)
    if not found:
        for url in allowed_urls:
            if url not in found:
                found.append(url)
            if len(found) == 3:
                break
    found = found[:3]
    body_without_sources = re.split(r"\n+\s*Источники\s*:", text, maxsplit=1, flags=re.IGNORECASE)[0]
    body_without_sources = URL_RE.sub("", body_without_sources)
    body_without_sources = re.sub(r"[ \t]+\n", "\n", body_without_sources).strip()
    if not found:
        return body_without_sources[:3500]
    footer = "Источники:\n" + "\n".join(found)
    room = 3500 - len(footer) - 2
    return body_without_sources[:room].rstrip() + "\n\n" + footer


def api_cost_usd(
    input_tokens: int,
    cached_tokens: int,
    output_tokens: int,
    embedding_tokens: int,
) -> float:
    uncached = max(0, input_tokens - cached_tokens)
    return (
        uncached / 1_000_000 * 2.0
        + cached_tokens / 1_000_000 * 0.20
        + output_tokens / 1_000_000 * 10.0
        + embedding_tokens / 1_000_000 * 0.02
    )
