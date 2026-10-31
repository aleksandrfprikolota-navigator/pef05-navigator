from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_DIR = ROOT / "knowledge"
PROMPT_PATH = ROOT / "prompts" / "system_prompt.txt"
SQL_PATH = ROOT / "sql" / "001_init.sql"


def load_dotenv(path: Path | None = None) -> None:
    env_path = path or (ROOT / ".env")
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Settings:
    telegram_token: str
    openai_api_key: str
    openai_base_url: str
    openai_model: str
    embedding_model: str
    owner_telegram_id: int
    database_url: str
    similarity_threshold: float
    monthly_budget_usd: float
    warn_budget_usd: float
    reasoning_effort: str


def get_settings() -> Settings:
    load_dotenv()
    owner = os.environ.get("OWNER_TELEGRAM_ID", "").strip()
    return Settings(
        telegram_token=os.environ.get("TELEGRAM_TOKEN", "").strip(),
        openai_api_key=os.environ.get("OPENAI_API_KEY", "").strip(),
        openai_base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").strip(),
        openai_model=os.environ.get("OPENAI_MODEL", "gpt-6-sol").strip(),
        embedding_model=os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small").strip(),
        owner_telegram_id=int(owner) if owner else 0,
        database_url=os.environ.get(
            "DATABASE_URL",
            "postgresql://navigator:navigator@localhost:5432/navigator",
        ).strip(),
        similarity_threshold=float(os.environ.get("SIMILARITY_THRESHOLD", "0.30")),
        monthly_budget_usd=float(os.environ.get("MONTHLY_BUDGET_USD", "100")),
        warn_budget_usd=float(os.environ.get("WARN_BUDGET_USD", "80")),
        reasoning_effort=os.environ.get("REASONING_EFFORT", "low").strip(),
    )
